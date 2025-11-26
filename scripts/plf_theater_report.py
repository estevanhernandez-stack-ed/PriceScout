#!/usr/bin/env python3
"""
PLF Theater Report Generator

Generates a report showing which company theaters have Premium Large Format (PLF)
screens and what types they are (IMAX, UltraScreen, Dolby, etc.)

Usage:
    python scripts/plf_theater_report.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict
from datetime import datetime

# Known PLF types (from ticket_types.json)
PLF_FORMATS = [
    "4DX", "D-BOX", "Dolby Cinema", "Grand Screen", "IMAX",
    "Prime", "RPX", "ScreenX", "Superscreen", "The Big House",
    "UltraScreen", "XD", "Premium Format", "PLF"
]


def get_plf_report():
    """Generate PLF theater report from database."""
    from app.db_adapter import get_session
    from app.db_models import Showing
    from sqlalchemy import distinct, func

    with get_session() as session:
        # Get all unique theater/format combinations
        results = session.query(
            Showing.theater_name,
            Showing.format,
            func.count('*').label('count')
        ).group_by(
            Showing.theater_name,
            Showing.format
        ).order_by(
            Showing.theater_name,
            Showing.format
        ).all()

        # Organize by theater
        theater_formats = defaultdict(lambda: {'plf_types': [], 'standard_formats': [], 'showing_counts': {}})

        for theater, fmt, count in results:
            if not fmt:
                continue

            theater_formats[theater]['showing_counts'][fmt] = count

            # Check if this is a PLF format
            fmt_upper = fmt.upper()
            is_plf = False

            for plf_type in PLF_FORMATS:
                if plf_type.upper() in fmt_upper or fmt_upper in plf_type.upper():
                    is_plf = True
                    if fmt not in theater_formats[theater]['plf_types']:
                        theater_formats[theater]['plf_types'].append(fmt)
                    break

            if not is_plf:
                if fmt not in theater_formats[theater]['standard_formats']:
                    theater_formats[theater]['standard_formats'].append(fmt)

        return dict(theater_formats)


def generate_report():
    """Generate and print the PLF theater report."""
    print("=" * 70)
    print("PLF THEATER REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    theater_data = get_plf_report()

    if not theater_data:
        print("No theater data found in database.")
        print("\nTo populate data, run a scrape in the application first.")
        return

    # Separate theaters with PLF from those without
    theaters_with_plf = {k: v for k, v in theater_data.items() if v['plf_types']}
    theaters_without_plf = {k: v for k, v in theater_data.items() if not v['plf_types']}

    # Report theaters with PLF
    print("THEATERS WITH PLF CAPABILITIES")
    print("-" * 70)

    if theaters_with_plf:
        for theater, data in sorted(theaters_with_plf.items()):
            plf_types = data['plf_types']
            print(f"\n{theater}")
            print(f"  PLF Types: {', '.join(plf_types)}")

            # Show showing counts for PLF
            plf_counts = [(fmt, data['showing_counts'].get(fmt, 0)) for fmt in plf_types]
            for fmt, count in plf_counts:
                print(f"    - {fmt}: {count} showings")
    else:
        print("  No theaters with PLF showings found in current data.")

    print()
    print("-" * 70)
    print("THEATERS WITHOUT PLF (Standard Only)")
    print("-" * 70)

    if theaters_without_plf:
        for theater, data in sorted(theaters_without_plf.items()):
            formats = data['standard_formats']
            print(f"\n{theater}")
            print(f"  Formats: {', '.join(formats) if formats else 'N/A'}")
    else:
        print("  All theaters have PLF capabilities.")

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total Theaters: {len(theater_data)}")
    print(f"Theaters with PLF: {len(theaters_with_plf)}")
    print(f"Theaters without PLF: {len(theaters_without_plf)}")

    if theaters_with_plf:
        # Collect all PLF types across theaters
        all_plf_types = set()
        for data in theaters_with_plf.values():
            all_plf_types.update(data['plf_types'])
        print(f"\nPLF Types Found: {', '.join(sorted(all_plf_types))}")

    print()


def generate_csv_report(output_path=None):
    """Generate CSV version of the PLF report."""
    import csv
    from io import StringIO

    theater_data = get_plf_report()

    if output_path is None:
        output_path = f"plf_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    rows = []
    for theater, data in sorted(theater_data.items()):
        has_plf = bool(data['plf_types'])
        plf_types = ', '.join(data['plf_types']) if data['plf_types'] else 'None'
        all_formats = ', '.join(sorted(set(data['plf_types'] + data['standard_formats'])))

        rows.append({
            'Theater': theater,
            'Has PLF': 'Yes' if has_plf else 'No',
            'PLF Types': plf_types,
            'All Formats': all_formats
        })

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Theater', 'Has PLF', 'PLF Types', 'All Formats'])
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV report saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Generate PLF Theater Report')
    parser.add_argument('--csv', action='store_true', help='Generate CSV output')
    parser.add_argument('--output', '-o', help='Output file path for CSV')

    args = parser.parse_args()

    if args.csv:
        generate_csv_report(args.output)
    else:
        generate_report()
