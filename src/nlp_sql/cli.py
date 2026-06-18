from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.table import Table

from nlp_sql.auth.service import authenticate_client
from nlp_sql.config import load_config
from nlp_sql.pipeline import answer_request

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
):
    """Run the API and chat UI at http://127.0.0.1:8000 (databases accessed only server-side)."""
    import uvicorn

    uvicorn.run("nlp_sql.api:app", host=host, port=port, reload=False)


@app.command("auth")
def auth_token(
    client_id: str = typer.Option(..., "--client-id", "-u"),
    client_secret: str = typer.Option(..., "--client-secret", "-s", hide_input=True),
    config: Optional[Path] = typer.Option(None, "--config", "-c"),
):
    """Get an opaque access token (capability only — no user profile)."""
    cfg = load_config(config)
    try:
        token, _grant = authenticate_client(cfg, client_id, client_secret)
    except PermissionError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    rprint("[green]Access token[/green] (use as Bearer or NLP_SQL_ACCESS_TOKEN):\n")
    rprint(token)


@app.command()
def query(
    text: str = typer.Argument(..., help="Natural language question / keywords"),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        "-t",
        envvar="NLP_SQL_ACCESS_TOKEN",
        help="Opaque access token from `nlp-sql auth`",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config.yaml",
    ),
    json_out: bool = typer.Option(False, "--json", help="Print JSON instead of a table"),
):
    """Schema-only LLM + read-only data API (token required)."""
    if not token:
        rprint(
            "[red]Missing access token.[/red] Run: nlp-sql auth --client-id ... --client-secret ...\n"
            "Or set NLP_SQL_ACCESS_TOKEN."
        )
        raise typer.Exit(1)

    try:
        result = answer_request(text, config_path=config, access_token=token)
    except PermissionError as e:
        rprint(f"[red]Forbidden:[/red] {e}")
        raise typer.Exit(1) from e
    except RuntimeError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from e

    if json_out:
        rprint(
            json.dumps(
                {
                    "sql": result.sql,
                    "column_names": result.column_names,
                    "rows": result.rows,
                    "database_ids_used": result.database_ids_used,
                    "explanation": result.explanation,
                    "retrieval": [
                        {
                            "db_id": h.db_id,
                            "table": h.table_name,
                            "score": h.score,
                        }
                        for h in result.retrieval_context
                    ],
                },
                default=str,
                indent=2,
            )
        )
        return

    if result.explanation:
        rprint(f"[dim]{result.explanation}[/dim]")
    if result.sql:
        rprint(f"[bold]SQL[/bold] ({', '.join(result.database_ids_used)}):\n{result.sql}\n")
    if not result.column_names:
        rprint("[yellow]No rows or no query produced.[/yellow]")
        return

    t = Table(*result.column_names, show_lines=True)
    for row in result.rows:
        t.add_row(*[str(row.get(c, "")) for c in result.column_names])
    rprint(t)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
