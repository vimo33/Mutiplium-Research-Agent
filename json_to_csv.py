#!/usr/bin/env python3
"""
Convert Multiplium research report JSON to CSV format.
Extracts all company data with sources and metadata.
"""

import json
import csv
import sys
from pathlib import Path
from typing import List, Dict, Any


def flatten_company_data(providers_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Flatten the nested provider -> segment -> company structure into a list of company records.
    """
    all_companies = []

    for provider in providers_data:
        provider_name = provider.get('provider', 'unknown')

        # Include Claude data but mark as unvalidated
        is_claude_raw = provider_name == 'anthropic'

        findings = provider.get('findings', [])
        for finding in findings:
            segment_name = finding.get('name', 'unknown')

            # Handle different data formats
            if is_claude_raw:
                # Claude has raw JSON string that needs parsing
                raw_content = finding.get('raw', '')
                if raw_content:
                    try:
                        # Extract JSON from markdown code blocks if present
                        import re
                        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', raw_content)
                        if json_match:
                            json_str = json_match.group(1)
                        else:
                            json_str = raw_content

                        parsed_data = json.loads(json_str)
                        if 'segments' in parsed_data:
                            companies = []
                            for seg in parsed_data['segments']:
                                seg_companies = seg.get('companies', [])
                                companies.extend(seg_companies)
                        else:
                            companies = []
                    except (json.JSONDecodeError, KeyError):
                        companies = []
                else:
                    companies = []
            else:
                # OpenAI and Google have direct companies array
                companies = finding.get('companies', [])
            for company in companies:
                # Create a flattened record
                record = {
                    'provider': provider_name,
                    'data_type': 'raw_unvalidated' if is_claude_raw else 'validated',
                    'segment': segment_name,
                    'company': company.get('company', ''),
                    'summary': company.get('summary', ''),
                    'website': company.get('website', ''),
                    'country': company.get('country', ''),
                    'region_state': company.get('region_state', ''),
                    'confidence_0to1': company.get('confidence_0to1', ''),
                    'vineyard_verified': company.get('vineyard_verified', ''),
                    'kpi_alignment_count': len(company.get('kpi_alignment', [])),
                    'sources_count': len(company.get('sources', [])),
                }

                # Add KPI alignments as separate columns
                kpi_list = company.get('kpi_alignment', [])
                for i in range(5):  # Max 5 KPIs
                    record[f'kpi_{i+1}'] = kpi_list[i] if i < len(kpi_list) else ''

                # Add sources as separate columns
                sources_list = company.get('sources', [])
                for i in range(5):  # Max 5 sources
                    record[f'source_{i+1}'] = sources_list[i] if i < len(sources_list) else ''

                all_companies.append(record)

    return all_companies


def main():
    if len(sys.argv) != 2:
        print("Usage: python json_to_csv.py <report.json>")
        sys.exit(1)

    json_file = Path(sys.argv[1])
    if not json_file.exists():
        print(f"Error: {json_file} not found")
        sys.exit(1)

    # Load JSON
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract providers data
    providers = data.get('providers', [])

    # Flatten company data
    companies = flatten_company_data(providers)

    # Define CSV headers
    headers = [
        'provider', 'data_type', 'segment', 'company', 'summary', 'website', 'country',
        'region_state', 'confidence_0to1', 'vineyard_verified',
        'kpi_alignment_count', 'sources_count',
        'kpi_1', 'kpi_2', 'kpi_3', 'kpi_4', 'kpi_5',
        'source_1', 'source_2', 'source_3', 'source_4', 'source_5'
    ]

    # Write CSV
    csv_file = json_file.with_suffix('.csv')
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(companies)

    print(f"✅ CSV created: {csv_file}")
    print(f"📊 Records: {len(companies)}")
    print(f"📋 Headers: {len(headers)}")


if __name__ == '__main__':
    main()
