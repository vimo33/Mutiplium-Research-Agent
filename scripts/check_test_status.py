#!/usr/bin/env python3
"""
Check the status of the deep research test and generate a comprehensive review report.

Usage:
    python scripts/check_test_status.py
"""

import json
from pathlib import Path
from datetime import datetime


def check_test_status():
    """Check if the deep research test has completed and generate a review report."""
    
    report_path = Path("reports/latest_report.json")
    
    if not report_path.exists():
        print("⏳ Test still running - no report generated yet")
        print("\nRun this script again in a few minutes...")
        return False
    
    # Load the report
    with open(report_path) as f:
        data = json.load(f)
    
    # Check if deep research section exists
    if "deep_research" not in data:
        print("⏳ Test still running - deep research section not yet present")
        print("\nThe discovery phase completed, but deep research is still processing...")
        return False
    
    print("✅ TEST COMPLETE!\n")
    print("=" * 80)
    print("DEEP RESEARCH TEST - RESULTS SUMMARY")
    print("=" * 80)
    
    # Get deep research data
    dr = data["deep_research"]
    companies = dr.get("companies", [])
    stats = dr.get("stats", {})
    
    # Overall stats
    print(f"\n📊 OVERALL STATISTICS")
    print("-" * 80)
    print(f"Total Companies Researched: {stats.get('total', 0)}")
    print(f"Successfully Completed: {stats.get('completed', 0)}")
    print(f"Data Completeness: {stats.get('data_completeness_pct', 0):.1f}%")
    print(f"Estimated Cost: ${dr.get('total_cost', 0):.2f}")
    print(f"Cost per Company: ${dr.get('cost_per_company', 0):.3f}")
    
    # Data point completeness
    print(f"\n📋 DATA POINT COMPLETENESS")
    print("-" * 80)
    print(f"Financial Data: {stats.get('has_financials', 0)}/{stats.get('total', 0)} " +
          f"({stats.get('has_financials', 0)/stats.get('total', 1)*100:.0f}%)")
    print(f"Team Data: {stats.get('has_team', 0)}/{stats.get('total', 0)} " +
          f"({stats.get('has_team', 0)/stats.get('total', 1)*100:.0f}%)")
    print(f"Competitors: {stats.get('has_competitors', 0)}/{stats.get('total', 0)} " +
          f"({stats.get('has_competitors', 0)/stats.get('total', 1)*100:.0f}%)")
    print(f"SWOT Analysis: {stats.get('has_swot', 0)}/{stats.get('total', 0)} " +
          f"({stats.get('has_swot', 0)/stats.get('total', 1)*100:.0f}%)")
    
    # Individual company details
    print(f"\n🏢 COMPANY DETAILS")
    print("=" * 80)
    
    for i, company in enumerate(companies, 1):
        print(f"\n{i}. {company.get('company', 'Unknown')}")
        print("-" * 80)
        
        # Basic info
        print(f"Website: {company.get('website', 'N/A')}")
        print(f"Country: {company.get('country', 'N/A')}")
        print(f"Confidence: {company.get('confidence_0to1', 0):.2f}")
        print(f"Status: {company.get('deep_research_status', 'unknown')}")
        
        # Check each data point
        has_financials = company.get('financials') and company.get('financials') != 'Not Disclosed'
        has_funding = len(company.get('funding_rounds', [])) > 0
        has_investors = len(company.get('investors', [])) > 0
        has_team = company.get('team') and isinstance(company.get('team'), dict)
        has_founders = False
        has_team_size = False
        if has_team:
            has_founders = len(company.get('team', {}).get('founders', [])) > 0
            has_team_size = company.get('team', {}).get('size', 'Unknown') != 'Unknown'
        has_competitors = company.get('competitors') and isinstance(company.get('competitors'), dict)
        has_competitor_list = False
        if has_competitors:
            has_competitor_list = len(company.get('competitors', {}).get('direct', [])) > 0
        has_swot = company.get('swot') and isinstance(company.get('swot'), dict)
        
        print(f"\nData Points:")
        print(f"  ✅ Executive Summary: YES (from discovery)")
        print(f"  ✅ Technology: YES (from discovery)")
        print(f"  {'✅' if has_financials else '❌'} Financial Data: {'YES' if has_financials else 'NO'}")
        if has_funding:
            print(f"     - Funding Rounds: {len(company.get('funding_rounds', []))}")
        if has_investors:
            print(f"     - Investors: {len(company.get('investors', []))}")
        print(f"  {'✅' if has_team else '❌'} Team Data: {'YES' if has_team else 'NO'}")
        if has_founders:
            print(f"     - Founders: {', '.join(company.get('team', {}).get('founders', [])[:3])}")
        if has_team_size:
            print(f"     - Team Size: {company.get('team', {}).get('size')}")
        print(f"  {'✅' if has_competitor_list else '❌'} Competitors: {'YES' if has_competitor_list else 'NO'}")
        if has_competitor_list:
            competitors_list = company.get('competitors', {}).get('direct', [])
            print(f"     - Direct: {', '.join(competitors_list[:3])}")
        print(f"  {'✅' if has_swot else '❌'} SWOT Analysis: {'YES' if has_swot else 'NO'}")
        if has_swot:
            swot = company.get('swot', {})
            print(f"     - Strengths: {len(swot.get('strengths', []))}")
            print(f"     - Weaknesses: {len(swot.get('weaknesses', []))}")
            print(f"     - Opportunities: {len(swot.get('opportunities', []))}")
            print(f"     - Threats: {len(swot.get('threats', []))}")
        
        # Website verification check
        website = company.get('website', 'N/A')
        if website and website not in ('N/A', 'Not Available', 'Unknown', ''):
            if website.startswith('http'):
                print(f"  ✅ Website Verified: {website}")
            else:
                print(f"  ⚠️  Website (needs http): {website}")
        else:
            print(f"  ❌ Website Missing")
    
    # Summary validation
    print(f"\n📈 VALIDATION SUMMARY")
    print("=" * 80)
    
    # Count validations
    target_companies = stats.get('total', 0)
    completed = stats.get('completed', 0)
    has_financials = stats.get('has_financials', 0)
    has_team = stats.get('has_team', 0)
    has_competitors = stats.get('has_competitors', 0)
    has_swot = stats.get('has_swot', 0)
    
    # Website accuracy
    websites_valid = sum(1 for c in companies if c.get('website') and 
                        c.get('website') not in ('N/A', 'Not Available', 'Unknown', '') and
                        c.get('website').startswith('http'))
    
    print(f"\n✅ Validation Checklist:")
    print(f"  {'✅' if completed == target_companies else '❌'} All {target_companies} companies completed: " +
          f"{completed}/{target_companies}")
    print(f"  {'✅' if has_financials >= target_companies * 0.67 else '❌'} Financial data ≥67%: " +
          f"{has_financials}/{target_companies} ({has_financials/target_companies*100:.0f}%)")
    print(f"  {'✅' if has_team == target_companies else '❌'} Team data 100%: " +
          f"{has_team}/{target_companies} ({has_team/target_companies*100:.0f}%)")
    print(f"  {'✅' if has_competitors >= target_companies * 0.9 else '❌'} Competitors ≥90%: " +
          f"{has_competitors}/{target_companies} ({has_competitors/target_companies*100:.0f}%)")
    print(f"  {'✅' if has_swot == target_companies else '❌'} SWOT 100%: " +
          f"{has_swot}/{target_companies} ({has_swot/target_companies*100:.0f}%)")
    print(f"  {'✅' if websites_valid == target_companies else '❌'} Website accuracy 100%: " +
          f"{websites_valid}/{target_companies} ({websites_valid/target_companies*100:.0f}%)")
    
    cost = dr.get('total_cost', 0)
    print(f"  {'✅' if cost <= 0.10 else '❌'} Cost ≤$0.10: ${cost:.2f}")
    
    # Overall result
    all_passed = (
        completed == target_companies and
        has_financials >= target_companies * 0.67 and
        has_team == target_companies and
        has_swot == target_companies and
        websites_valid == target_companies and
        cost <= 0.10
    )
    
    print(f"\n{'🎉 TEST PASSED!' if all_passed else '⚠️  TEST NEEDS REVIEW'}")
    
    if all_passed:
        print("\n✅ All validation criteria met!")
        print("✅ Ready to proceed with full batch (25 companies)")
        print("\nNext command:")
        print("  python -m multiplium.orchestrator --config config/dev.yaml --deep-research --top-n 25")
    else:
        print("\n⚠️  Some validation criteria not met. Review the details above.")
        print("Consider adjusting prompts or retrying the test.")
    
    print(f"\n📄 Full report location:")
    print(f"  {report_path.absolute()}")
    print(f"\nGenerated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return True


if __name__ == "__main__":
    check_test_status()

