#!/usr/bin/env python3
"""Create two sample SQLite files under ./data for demo and local testing."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)

    sales = data / "sales.db"
    conn = sqlite3.connect(sales)
    c = conn.cursor()
    c.executescript(
        """
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS customers;
        CREATE TABLE customers (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          region TEXT,
          created_at TEXT
        );
        CREATE TABLE orders (
          id INTEGER PRIMARY KEY,
          customer_id INTEGER NOT NULL,
          order_date TEXT,
          status TEXT,
          total_amount REAL
        );
        CREATE TABLE order_items (
          id INTEGER PRIMARY KEY,
          order_id INTEGER NOT NULL,
          product_name TEXT,
          quantity INTEGER,
          unit_price REAL
        );
        """
    )
    c.executemany(
        "INSERT INTO customers (id, name, region, created_at) VALUES (?,?,?,?)",
        [
            (1, "Acme Corp", "US-West", "2024-01-10"),
            (2, "Globex", "EU", "2024-02-01"),
            (3, "Initech", "US-East", "2024-03-15"),
        ],
    )
    c.executemany(
        "INSERT INTO orders (id, customer_id, order_date, status, total_amount) VALUES (?,?,?,?,?)",
        [
            (101, 1, "2024-04-01", "shipped", 120.5),
            (102, 2, "2024-04-02", "open", 45.0),
            (103, 1, "2024-04-05", "shipped", 80.0),
        ],
    )
    c.executemany(
        "INSERT INTO order_items (id, order_id, product_name, quantity, unit_price) VALUES (?,?,?,?,?)",
        [
            (1, 101, "Widget A", 2, 25.0),
            (2, 101, "Widget B", 1, 70.5),
            (3, 102, "Gadget", 1, 45.0),
            (4, 103, "Widget A", 3, 25.0),
            (5, 103, "Cable", 1, 5.0),
        ],
    )
    conn.commit()
    conn.close()

    hr = data / "hr.db"
    conn = sqlite3.connect(hr)
    c = conn.cursor()
    c.executescript(
        """
        DROP TABLE IF EXISTS employees;
        CREATE TABLE employees (
          id INTEGER PRIMARY KEY,
          full_name TEXT NOT NULL,
          department TEXT,
          title TEXT,
          salary REAL,
          hired_on TEXT
        );
        """
    )
    c.executemany(
        "INSERT INTO employees (id, full_name, department, title, salary, hired_on) VALUES (?,?,?,?,?,?)",
        [
            (1, "Alice Johnson", "Engineering", "Senior Developer", 145000, "2019-03-01"),
            (2, "Bob Smith", "Sales", "Account Executive", 95000, "2021-07-10"),
            (3, "Carol Xu", "HR", "Manager", 110000, "2018-11-20"),
        ],
    )
    conn.commit()
    conn.close()

    print(f"Wrote {sales} and {hr}")


if __name__ == "__main__":
    main()
