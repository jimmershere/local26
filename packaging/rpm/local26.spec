Name:           local26
Version:        0.1.0
Release:        1%{?dist}
Summary:        Local-26 deployment control plane

License:        Proprietary
URL:            https://example.invalid/local26
BuildArch:      noarch

# Current codebase requires Python 3.12+. On RHEL8 this usually means a custom
# builder/runtime or an internal python3.12 package stream.
BuildRequires:  python3.12
BuildRequires:  python3.12-pip
BuildRequires:  python3.12-setuptools
BuildRequires:  python3.12-wheel
BuildRequires:  python3.12-devel
BuildRequires:  rpm-build
Requires:       /bin/bash
Requires:       python3.12
Requires:       python3.12dist(pyyaml) >= 6.0
Requires(pre):  shadow-utils

Source0:        %{name}-%{version}.tar.gz

%global app_root /opt/local26
%global app_lib %{app_root}/app
%global app_venv %{app_root}/venv

%description
Local-26 is a Python-based deployment and operator control plane for generating
plans, validating deploys, and running controlled workflow operations.

This first RPM scaffold installs Local-26 under /opt/local26, exposes /usr/bin/local26,
and provisions /etc/local26 and /var/lib/local26 for runtime configuration and data.

%prep
%autosetup -n %{name}-%{version}

%build
python3.12 -m venv build-venv
source build-venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install .

%install
rm -rf %{buildroot}
install -d %{buildroot}%{app_lib}
cp -a bin docs src pyproject.toml README.md Makefile %{buildroot}%{app_lib}/

python3.12 -m venv %{buildroot}%{app_venv}
source %{buildroot}%{app_venv}/bin/activate
pip install --upgrade pip setuptools wheel
pip install %{buildroot}%{app_lib}

install -d %{buildroot}%{_bindir}
install -m 0755 packaging/rpm/scripts/local26-wrapper %{buildroot}%{_bindir}/local26

install -d %{buildroot}%{_sysconfdir}/local26
install -m 0644 packaging/rpm/local26.ini %{buildroot}%{_sysconfdir}/local26/local26.ini.example

install -d %{buildroot}%{_sharedstatedir}/local26
install -d %{buildroot}%{_localstatedir}/lib/local26
install -d %{buildroot}%{_docdir}/%{name}
install -m 0644 packaging/rpm/README.md %{buildroot}%{_docdir}/%{name}/

%pre
getent group local26 >/dev/null || groupadd -r local26
getent passwd local26 >/dev/null || useradd -r -g local26 -d /var/lib/local26 -s /sbin/nologin -c "Local-26 service account" local26
exit 0

%files
%doc %{_docdir}/%{name}/README.md
%dir %{app_root}
%dir %{app_lib}
%dir %{app_venv}
%{app_lib}/README.md
%{app_lib}/Makefile
%{app_lib}/pyproject.toml
%{app_lib}/bin
%{app_lib}/docs
%{app_lib}/src
%{app_venv}
%{_bindir}/local26
%dir %{_sysconfdir}/local26
%config(noreplace) %{_sysconfdir}/local26/local26.ini.example
%dir %{_sharedstatedir}/local26
%dir %{_localstatedir}/lib/local26

%post
chown -R local26:local26 %{_localstatedir}/lib/local26 %{_sharedstatedir}/local26 || true
exit 0

%changelog
* Tue Apr 21 2026 OpenClaw <openclaw@example.invalid> - 0.1.0-1
- Initial RPM packaging scaffold
