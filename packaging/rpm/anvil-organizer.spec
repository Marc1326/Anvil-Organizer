Name:           anvil-organizer
Version:        1.2.2
Release:        1%{?dist}
Summary:        Native Linux Mod Manager inspired by Mod Organizer 2

License:        GPL-3.0-or-later
URL:            https://github.com/Marc1326/Anvil-Organizer
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
BuildRequires:  python3-pip

Requires:       python3 >= 3.11
Requires:       python3-pyside6
Requires:       python3-lz4
Requires:       qt6-qtbase
Requires:       hicolor-icon-theme

%description
Anvil Organizer is a native Linux mod manager for games like Skyrim,
Fallout 4, Cyberpunk 2077, Baldur's Gate 3, Starfield, and more.
Inspired by Mod Organizer 2, it features virtual file system deployment,
profile management, Nexus Mods integration, and plugin load ordering.

%prep
%autosetup -n Anvil-Organizer-%{version}

%build
# Nothing to build — pure Python package

%install
pip3 install --no-build-isolation --no-deps --root=%{buildroot} --prefix=/usr .

# Desktop entry
install -Dm644 anvil-organizer.desktop \
    %{buildroot}%{_datadir}/applications/anvil-organizer.desktop

# Icons
install -Dm644 anvil/resources/logo.png \
    %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/anvil-organizer.png
install -Dm644 anvil/resources/logo.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/anvil-organizer.svg

%files
%license LICENSE
%doc README.md
%{_bindir}/anvil-organizer
%{python3_sitelib}/anvil/
%{python3_sitelib}/anvil_organizer-*.egg-info/
%{_datadir}/applications/anvil-organizer.desktop
%{_datadir}/icons/hicolor/256x256/apps/anvil-organizer.png
%{_datadir}/icons/hicolor/scalable/apps/anvil-organizer.svg

%changelog
* Sat Mar 28 2026 Marc <marc1326@users.noreply.github.com> - 1.2.2-1
- Flatpak and packaging improvements
- LOOT integration
- Deploy filter

* Sat Mar 28 2026 Marc <marc1326@users.noreply.github.com> - 1.2.1-1
- Collection Export: direct native file dialog
- Fix: Card click in Export/Import dialog

* Fri Mar 27 2026 Marc <marc1326@users.noreply.github.com> - 1.2.0-1
- Initial release
