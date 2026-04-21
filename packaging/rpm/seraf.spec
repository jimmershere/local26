Name:           seraf
Version:        0.1.0
Release:        1%{?dist}
Summary:        Seraf deployment control plane

License:        Proprietary
URL:            https://example.invalid/seraf
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

%global app_root /opt/seraf
%global app_lib %{app_root}/app
%global app_venv %{app_root}/venv

%description
Seraf is a Python-based deployment and operator control plane for generating
plans, validating deploys, and running controlled workflow operations.

This first RPM scaffold installs Seraf under /opt/seraf, exposes /usr/bin/seraf,
and provisions /etc/seraf and /var/lib/seraf for runtime configuration and data.

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
install -m 0755 packaging/rpm/scripts/seraf-wrapper %{buildroot}%{_bindir}/seraf

install -d %{buildroot}%{_sysconfdir}/seraf
install -m 0644 packaging/rpm/seraf.ini %{buildroot}%{_sysconfdir}/seraf/seraf.ini.example

install -d %{buildroot}%{_sharedstatedir}/seraf
install -d %{buildroot}%{_localstatedir}/lib/seraf
install -d %{buildroot}%{_docdir}/%{name}
install -m 0644 packaging/rpm/README.md %{buildroot}%{_docdir}/%{name}/

%pre
getent group seraf >/dev/null || groupadd -r seraf
getent passwd seraf >/dev/null || useradd -r -g seraf -d /var/lib/seraf -s /sbin/nologin -c "Seraf service account" seraf
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
%{_bindir}/seraf
%dir %{_sysconfdir}/seraf
%config(noreplace) %{_sysconfdir}/seraf/seraf.ini.example
%dir %{_sharedstatedir}/seraf
%dir %{_localstatedir}/lib/seraf

%post
chown -R seraf:seraf %{_localstatedir}/lib/seraf %{_sharedstatedir}/seraf || true
exit 0

%changelog
* Tue Apr 21 2026 OpenClaw <openclaw@example.invalid> - 0.1.0-1
- Initial RPM packaging scaffold
