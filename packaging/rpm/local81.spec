Name:           local81
Version:        0.1.0
Release:        1%{?dist}
Summary:        Local-81 deployment control plane

License:        Proprietary
URL:            https://example.invalid/local81
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

%global app_root /opt/local81
%global app_lib %{app_root}/app
%global app_venv %{app_root}/venv

%description
Local-81 is a Python-based deployment and operator control plane for generating
plans, validating deploys, and running controlled workflow operations.

This first RPM scaffold installs Local-81 under /opt/local81, exposes /usr/bin/local81,
and provisions /etc/local81 and /var/lib/local81 for runtime configuration and data.

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
install -m 0755 packaging/rpm/scripts/local81-wrapper %{buildroot}%{_bindir}/local81

install -d %{buildroot}%{_sysconfdir}/local81
install -m 0644 packaging/rpm/local81.ini %{buildroot}%{_sysconfdir}/local81/local81.ini.example

install -d %{buildroot}%{_sharedstatedir}/local81
install -d %{buildroot}%{_localstatedir}/lib/local81
install -d %{buildroot}%{_docdir}/%{name}
install -m 0644 packaging/rpm/README.md %{buildroot}%{_docdir}/%{name}/

%pre
getent group local81 >/dev/null || groupadd -r local81
getent passwd local81 >/dev/null || useradd -r -g local81 -d /var/lib/local81 -s /sbin/nologin -c "Local-81 service account" local81
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
%{_bindir}/local81
%dir %{_sysconfdir}/local81
%config(noreplace) %{_sysconfdir}/local81/local81.ini.example
%dir %{_sharedstatedir}/local81
%dir %{_localstatedir}/lib/local81

%post
chown -R local81:local81 %{_localstatedir}/lib/local81 %{_sharedstatedir}/local81 || true
exit 0

%changelog
* Tue Apr 21 2026 OpenClaw <openclaw@example.invalid> - 0.1.0-1
- Initial RPM packaging scaffold
