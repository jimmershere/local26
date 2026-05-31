from __future__ import annotations

from local81.policy import compliance_findings


def run_compliance_report() -> int:
    findings = compliance_findings()
    passes = [finding for finding in findings if finding.level == "PASS"]
    warns = [finding for finding in findings if finding.level == "WARN"]
    fails = [finding for finding in findings if finding.level == "FAIL"]
    print("Local-81 compliance report")
    print("==========================")
    print("Profile: NIST/CMS-style operational hardening")
    print(f"Checked {len(findings)} controls: {len(passes)} pass, {len(warns)} warnings, {len(fails)} failures.\n")
    for finding in findings:
        print(f"  {finding.render()}")
    if fails:
        print("\nCompliance report found blocking access-control issues.")
        return 1
    if warns:
        print("\nCompliance report found hardening gaps to review.")
        return 0
    print("\nCompliance hardening controls look ready.")
    return 0
