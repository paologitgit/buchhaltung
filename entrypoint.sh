#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py loaddata kontenrahmen_ch_kmu vat_codes_ch kontengruppen
python manage.py collectstatic --noinput

exec "$@"
