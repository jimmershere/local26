from __future__ import annotations

import re
from pathlib import Path

from .catalog import get_rule
from .models import ComplianceFinding


TEXT_EXTS = {".conf", ".xml", ".properties", ".sh", ".service", ".yml", ".yaml", ".dockerfile", ""}
WEAK_CIPHER_RE = re.compile(r"\b(NULL|aNULL|eNULL|EXPORT|DES|3DES|RC4|MD5|LOW|MEDIUM)\b", re.IGNORECASE)


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _read(path: Path) -> str | None:
    if path.stat().st_size > 512_000:
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _finding(rule_id: str, status: str, path: Path, root: Path, message: str, evidence: list[str] | None = None) -> ComplianceFinding:
    rule = get_rule(rule_id)
    return ComplianceFinding(
        rule_id=rule.rule_id,
        title=rule.title,
        status=status,
        severity=rule.severity if status != "pass" else "info",
        category=rule.category,
        subject=_rel(root, path),
        message=message,
        controls=list(rule.controls),
        evidence=evidence or [],
        remediation=rule.remediation,
        source="web-java",
        location=_rel(root, path),
        confidence="medium",
    )


def _iter_text_files(root: Path) -> list[Path]:
    excluded = {".git", "node_modules", "dist", "build", "coverage", "__pycache__"}
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in excluded for part in path.parts):
            continue
        if path.is_file() and (path.suffix.lower() in TEXT_EXTS or path.name.startswith("Dockerfile") or path.name in {"Caddyfile"}):
            files.append(path)
    return files


def _scan_apache(path: Path, root: Path, text: str) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    lower = text.lower()
    if "sslprotocol" in lower:
        bad = any(token in lower for token in ("sslv2", "sslv3", "tlsv1 ", "tlsv1.0", "tlsv1.1"))
        findings.append(_finding("WEB_TLS_PROTOCOLS_MIN_12", "fail" if bad else "pass", path, root, "Apache SSLProtocol reviewed"))
    if "sslciphersuite" in lower and WEAK_CIPHER_RE.search(text):
        findings.append(_finding("WEB_TLS_WEAK_CIPHERS_DISABLED", "fail", path, root, "weak cipher token appears in SSLCipherSuite"))
    if "strict-transport-security" in lower:
        findings.append(_finding("WEB_HSTS_ENABLED", "pass", path, root, "HSTS header evidence found"))
    if "traceenable on" in lower:
        findings.append(_finding("APACHE_TRACE_DISABLED", "fail", path, root, "TraceEnable On found"))
    elif "traceenable off" in lower:
        findings.append(_finding("APACHE_TRACE_DISABLED", "pass", path, root, "TraceEnable Off found"))
    if "servertokens prod" in lower or "serversignature off" in lower:
        findings.append(_finding("WEB_SERVER_TOKENS_MINIMIZED", "pass", path, root, "Apache banner minimization evidence found"))
    elif "servertokens full" in lower or "serversignature on" in lower:
        findings.append(_finding("WEB_SERVER_TOKENS_MINIMIZED", "fail", path, root, "verbose Apache server banner directive found"))
    if "customlog" in lower and "errorlog" in lower:
        findings.append(_finding("WEB_ACCESS_ERROR_LOGGING_ENABLED", "pass", path, root, "Apache access and error logging directives found"))
    return findings


def _scan_nginx(path: Path, root: Path, text: str) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    lower = text.lower()
    if "ssl_protocols" in lower:
        bad = any(token in lower for token in ("tlsv1 ", "tlsv1.0", "tlsv1.1", "sslv3"))
        findings.append(_finding("WEB_TLS_PROTOCOLS_MIN_12", "fail" if bad else "pass", path, root, "Nginx ssl_protocols reviewed"))
    if "ssl_ciphers" in lower and WEAK_CIPHER_RE.search(text):
        findings.append(_finding("WEB_TLS_WEAK_CIPHERS_DISABLED", "fail", path, root, "weak cipher token appears in ssl_ciphers"))
    if "strict-transport-security" in lower:
        findings.append(_finding("WEB_HSTS_ENABLED", "pass", path, root, "HSTS header evidence found"))
    security_headers = ("x-content-type-options", "content-security-policy", "referrer-policy", "permissions-policy")
    if any(header in lower for header in security_headers):
        findings.append(_finding("WEB_SECURITY_HEADERS_PRESENT", "pass", path, root, "browser security header evidence found"))
    if "server_tokens off" in lower:
        findings.append(_finding("WEB_SERVER_TOKENS_MINIMIZED", "pass", path, root, "server_tokens off found"))
    elif "server_tokens on" in lower:
        findings.append(_finding("WEB_SERVER_TOKENS_MINIMIZED", "fail", path, root, "server_tokens on found"))
    if "access_log off" in lower:
        findings.append(_finding("WEB_ACCESS_ERROR_LOGGING_ENABLED", "fail", path, root, "access_log off found"))
    elif "access_log" in lower or "error_log" in lower:
        findings.append(_finding("WEB_ACCESS_ERROR_LOGGING_ENABLED", "pass", path, root, "Nginx logging directive found"))
    if any(token in lower for token in ("client_body_timeout", "client_header_timeout", "send_timeout", "keepalive_timeout")):
        findings.append(_finding("WEB_TIMEOUTS_CONFIGURED", "pass", path, root, "Nginx timeout directive found"))
    return findings


def _scan_tomcat(path: Path, root: Path, text: str) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    lower = text.lower()
    if "server.xml" in path.name.lower() or "<server" in lower:
        if 'port="8005"' in lower and 'shutdown="shutdown"' in lower:
            findings.append(_finding("TOMCAT_SHUTDOWN_PORT_DISABLED", "fail", path, root, "default Tomcat shutdown port and token found"))
        elif 'port="-1"' in lower:
            findings.append(_finding("TOMCAT_SHUTDOWN_PORT_DISABLED", "pass", path, root, "Tomcat shutdown port disabled"))
        if 'allowtrace="true"' in lower:
            findings.append(_finding("APACHE_TRACE_DISABLED", "fail", path, root, "Tomcat allowTrace=true found"))
        if "accesslogvalve" in lower:
            findings.append(_finding("WEB_ACCESS_ERROR_LOGGING_ENABLED", "pass", path, root, "Tomcat AccessLogValve found"))
        if 'autodeploy="true"' in lower:
            findings.append(_finding("TOMCAT_MANAGER_DEFAULT_APPS_RESTRICTED", "warn", path, root, "Tomcat autoDeploy=true requires production review"))
    if "jdwp" in lower or "-xrunjdwp" in lower:
        findings.append(_finding("JVM_REMOTE_DEBUG_DISABLED", "fail", path, root, "JVM remote debug flag found"))
    if "jmxremote" in lower and ("authenticate=false" in lower or "ssl=false" in lower):
        findings.append(_finding("JVM_JMX_SECURED", "fail", path, root, "JMX remote management lacks auth or TLS"))
    if "tomcat-users" in path.name.lower() and re.search(r'password="(?:tomcat|admin|manager|password|changeme)"', lower):
        findings.append(_finding("TOMCAT_MANAGER_DEFAULT_APPS_RESTRICTED", "fail", path, root, "weak/default Tomcat manager credential found"))
    return findings


def scan_web_java(root: Path) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    for path in _iter_text_files(root):
        try:
            text = _read(path)
        except OSError:
            continue
        if text is None:
            continue
        lower_name = path.name.lower()
        rel = _rel(root, path).lower()
        if "apache" in rel or "httpd" in rel or "sslprotocol" in text.lower() or "traceenable" in text.lower():
            findings.extend(_scan_apache(path, root, text))
        if "nginx" in rel or "ssl_protocols" in text.lower() or "server_tokens" in text.lower():
            findings.extend(_scan_nginx(path, root, text))
        if "tomcat" in rel or lower_name in {"server.xml", "tomcat-users.xml", "setenv.sh"} or "catalina_opts" in text.lower():
            findings.extend(_scan_tomcat(path, root, text))
    for app_name in ("manager", "host-manager", "docs", "examples"):
        for path in root.rglob(app_name):
            if path.is_dir() and "webapps" in path.parts:
                findings.append(_finding("TOMCAT_MANAGER_DEFAULT_APPS_RESTRICTED", "warn", path, root, f"Tomcat default application directory {app_name} found"))
    return findings
