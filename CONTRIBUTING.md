# Contributing to Anvil Organizer

Thanks for your interest in contributing! Anvil Organizer is an open-source Linux mod manager and we welcome contributions of all kinds.

## How to Contribute

### Reporting Bugs

- Use the [Bug Report](https://github.com/Marc1326/Anvil-Organizer/issues/new?template=bug_report.md) template
- Include your Linux distro, Anvil version, and the game you're modding
- Paste terminal output or screenshots if possible

### Suggesting Features

- Use the [Feature Request](https://github.com/Marc1326/Anvil-Organizer/issues/new?template=feature_request.md) template
- Check existing issues first to avoid duplicates
- Describe your use case — *why* you need it, not just *what*

### Code Contributions

1. **Open an issue first** to discuss what you'd like to change
2. Fork the repository
3. Create a feature branch (`git checkout -b feat/my-feature`)
4. Make your changes
5. Test with `./restart.sh` — ensure no tracebacks
6. Commit with a descriptive message
7. Open a Pull Request

### Adding Game Support

Anvil has an open plugin system — you can add new games without touching core code:

- **No coding?** Use **File → Create Game Plugin** in the app
- **With code?** Create a plugin in `anvil/plugins/games/` — see existing plugins for reference

### Translations

Anvil supports 7 languages (DE, EN, ES, FR, IT, PT, RU). Translation files are in `anvil/locales/`. If you'd like to improve a translation or add a new language, PRs are welcome.

## Development Setup

```bash
git clone https://github.com/Marc1326/Anvil-Organizer.git
cd Anvil-Organizer
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Code Style

- Python 3.11+, PySide6/Qt6
- No `setStyleSheet()` in widgets — themes are inherited via QSS
- Use `tr()` for all user-facing strings
- Read paths from instance config — no hardcoded paths

## License

By contributing, you agree that your contributions will be licensed under the [GPL-3.0 License](LICENSE).
