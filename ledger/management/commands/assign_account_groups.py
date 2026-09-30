from django.core.management.base import BaseCommand

from ledger.models import Account, AccountGroup

# code -> (Saldobilanz-Gruppencode oder None, Jahresrechnung-Gruppencode oder None)
# Deckt sowohl den mitgelieferten Standard-Kontenrahmen als auch gängige,
# von Treuhändern oft ergänzte Konten ab (z.B. Kontokorrent-Verrechnungen,
# Sozialversicherungsaufwand-Splits). Konten mit unklarer/eigenwilliger
# Zuordnung (z.B. Vorsteuer, Privatbezüge, ausserordentlicher Aufwand) werden
# bewusst nicht automatisch zugeordnet -- das bleibt Handarbeit im Kontenplan.
CODE_MAP = {
    "1000": ("100", "FLUESSIGE_MITTEL"),
    "1020": ("100", "FLUESSIGE_MITTEL"),
    "1100": ("110", "FORDERUNGEN_LL"),
    "1300": ("130", "AKTIVE_RA"),
    "1500": ("150", "MOBILE_SACHANLAGEN"),
    "1510": ("150", "MOBILE_SACHANLAGEN"),
    "1530": ("150", "MOBILE_SACHANLAGEN"),
    "2000": ("200", "VERB_LL"),
    "2140": ("210", "KURZFR_VERZINSLICH"),
    "2200": ("220", "UEBRIGE_KURZFR_VERB"),
    "2271": ("220", "UEBRIGE_KURZFR_VERB"),
    "2274": ("220", "UEBRIGE_KURZFR_VERB"),
    "2300": ("230", "PASSIVE_RA"),
    "2480": ("114", "UEBRIGE_FORDERUNGEN"),
    "2800": ("280", "STAMMKAPITAL"),
    "2950": ("290", "GESETZLICHE_RESERVE"),
    "2970": ("290", "GEWINNVORTRAG"),
    "3000": ("30", "BRUTTOERTRAG"),
    "3400": ("30", "BRUTTOERTRAG"),
    "4000": ("40", "MATERIALAUFWAND"),
    "4200": ("40", "MATERIALAUFWAND"),
    "4400": ("40", "MATERIALAUFWAND"),
    "5000": ("50", "PERSONALAUFWAND"),
    "5700": ("57", "PERSONALAUFWAND"),
    "5730": ("57", "PERSONALAUFWAND"),
    "6000": ("670", "UEBRIGER_BETRIEBSAUFWAND"),
    "6100": ("610", "UEBRIGER_BETRIEBSAUFWAND"),
    "6110": ("610", "UEBRIGER_BETRIEBSAUFWAND"),
    "6200": ("620", "UEBRIGER_BETRIEBSAUFWAND"),
    "6300": ("630", "UEBRIGER_BETRIEBSAUFWAND"),
    "6360": ("630", "UEBRIGER_BETRIEBSAUFWAND"),
    "6400": ("640", "UEBRIGER_BETRIEBSAUFWAND"),
    "6460": ("640", "UEBRIGER_BETRIEBSAUFWAND"),
    "6500": ("650", "UEBRIGER_BETRIEBSAUFWAND"),
    "6510": ("650", "UEBRIGER_BETRIEBSAUFWAND"),
    "6520": ("650", "UEBRIGER_BETRIEBSAUFWAND"),
    "6530": ("650", "UEBRIGER_BETRIEBSAUFWAND"),
    "6570": ("650", "UEBRIGER_BETRIEBSAUFWAND"),
    "6600": ("670", "UEBRIGER_BETRIEBSAUFWAND"),
    "6700": ("670", "UEBRIGER_BETRIEBSAUFWAND"),
    "6750": ("675", "UEBRIGER_BETRIEBSAUFWAND"),
    "6800": ("680", "ABSCHREIBUNGEN"),
    "6821": ("680", "ABSCHREIBUNGEN"),
    "6823": ("680", "ABSCHREIBUNGEN"),
    "6900": ("690", "FINANZERFOLG"),
    "6940": ("690", "FINANZERFOLG"),
    "6950": ("690", "FINANZERFOLG"),
    "8900": ("890", "STEUERN"),
}


class Command(BaseCommand):
    help = (
        "Ordnet Konten anhand ihres Codes automatisch einer Saldobilanz- und/oder "
        "Jahresrechnung-Kontengruppe zu (Standard-Kontenrahmen und gängige "
        "Erweiterungen). Bestehende Zuordnungen werden nicht überschrieben, ausser "
        "mit --force. Konten ohne bekannten Code bleiben unverändert -- diese "
        "weist du manuell im Kontenplan (Admin) zu."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true", help="Auch bereits zugeordnete Konten überschreiben."
        )

    def handle(self, *args, **options):
        saldobilanz_groups = {g.code: g for g in AccountGroup.objects.filter(tree=AccountGroup.Tree.SALDOBILANZ)}
        jahresrechnung_groups = {
            g.code: g for g in AccountGroup.objects.filter(tree=AccountGroup.Tree.JAHRESRECHNUNG)
        }

        updated = 0
        skipped_unknown = []
        skipped_existing = []

        for account in Account.objects.all():
            mapping = CODE_MAP.get(account.code)
            if not mapping:
                skipped_unknown.append(account.code)
                continue

            saldobilanz_code, jahresrechnung_code = mapping
            update_fields = []

            if saldobilanz_code and (options["force"] or account.saldobilanz_gruppe_id is None):
                group = saldobilanz_groups.get(saldobilanz_code)
                if group and account.saldobilanz_gruppe_id != group.id:
                    account.saldobilanz_gruppe = group
                    update_fields.append("saldobilanz_gruppe")
            elif account.saldobilanz_gruppe_id is not None:
                skipped_existing.append(account.code)

            if jahresrechnung_code and (options["force"] or account.jahresrechnung_gruppe_id is None):
                group = jahresrechnung_groups.get(jahresrechnung_code)
                if group and account.jahresrechnung_gruppe_id != group.id:
                    account.jahresrechnung_gruppe = group
                    update_fields.append("jahresrechnung_gruppe")

            if update_fields:
                account.save(update_fields=update_fields)
                updated += 1

        self.stdout.write(self.style.SUCCESS(f"{updated} Konto(en) einer Gruppe zugeordnet."))
        if skipped_unknown:
            self.stdout.write(
                "Ohne bekannte Standard-Zuordnung (bitte manuell im Kontenplan zuweisen): "
                + ", ".join(sorted(set(skipped_unknown)))
            )
