# Translation files

Generate message files for Spanish and French:

    python manage.py makemessages -l es -l fr

Edit the generated `.po` files in `es/LC_MESSAGES/` and `fr/LC_MESSAGES/`, then compile:

    python manage.py compilemessages

Use `{% trans "text" %}` or `{% blocktrans %}...{% endblocktrans %}` in templates, and `gettext` / `_()` in Python code for translatable strings.
