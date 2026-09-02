import csv
import re
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from lxml_html_clean import Cleaner

from core.models import Article


REQUIRED_HEADERS = {'ArticleID', 'Title', 'Content', 'LastUpdated'}

# Strips scripts/event handlers/dangerous tags while keeping formatting markup
# (including inline style attributes) intact for the legacy article content.
_cleaner = Cleaner(
    scripts=True,
    javascript=True,
    comments=True,
    style=False,
    inline_style=False,
    links=False,
    meta=True,
    page_structure=True,
    processing_instructions=True,
    embedded=True,
    frames=True,
    forms=True,
    annoying_tags=True,
    remove_unknown_tags=False,
    safe_attrs_only=True,
    safe_attrs=Cleaner.safe_attrs | frozenset(['style']),
)


def sanitize_html(raw_html):
    if not raw_html or not raw_html.strip():
        return ''
    return _cleaner.clean_html(f'<div>{raw_html}</div>')


def parse_last_updated(value):
    match = re.search(r'Last Updated:\s*(.+)', value or '')
    text = match.group(1).strip() if match else (value or '').strip()
    try:
        naive = datetime.strptime(text, '%m/%d/%Y %I:%M:%S %p')
    except ValueError:
        return None
    return timezone.make_aware(naive)


class Command(BaseCommand):
    help = 'Import legacy news_content.csv rows as Article pages.'

    def add_arguments(self, parser):
        parser.add_argument(
            'source',
            nargs='?',
            default='old_data/news_content.csv',
            help='Path to the news_content.csv export.',
        )
        parser.add_argument('--dry-run', action='store_true', help='Parse and validate without writing to the database.')

    def handle(self, *args, **options):
        path = Path(options['source'])
        if not path.exists():
            raise CommandError(f'{path} does not exist.')

        with path.open('r', encoding='cp1252', newline='') as handle:
            reader = csv.DictReader(handle)
            missing = REQUIRED_HEADERS - set(reader.fieldnames or [])
            if missing:
                raise CommandError(f'{path} is missing required headers: {", ".join(sorted(missing))}')
            rows = list(reader)

        existing_slugs = set(Article.objects.values_list('slug', flat=True))
        created, updated = 0, 0

        with transaction.atomic():
            for row_number, row in enumerate(rows, start=2):
                article_id = row.get('ArticleID', '').strip()
                title = row.get('Title', '').strip()
                if not article_id or not title:
                    self.stderr.write(f'row {row_number}: skipped, missing ArticleID or Title')
                    continue

                legacy_article_id = int(article_id)
                content = sanitize_html(row.get('Content', ''))
                published_at = parse_last_updated(row.get('LastUpdated', ''))

                article = Article.objects.filter(legacy_article_id=legacy_article_id).first()
                if article is None:
                    slug = self._unique_slug(title, existing_slugs)
                    existing_slugs.add(slug)
                    article = Article(legacy_article_id=legacy_article_id, slug=slug)
                    created += 1
                else:
                    updated += 1

                article.title = title
                article.content = content
                article.published_at = published_at
                article.save()

                if options['dry_run']:
                    transaction.set_rollback(True)

        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(
                f'Dry run: would create {created} and update {updated} article(s).'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Imported news articles: {created} created, {updated} updated.'
            ))

    @staticmethod
    def _unique_slug(title, existing_slugs):
        base = slugify(title)[:250] or 'article'
        slug = base
        suffix = 2
        while slug in existing_slugs:
            slug = f'{base}-{suffix}'[:255]
            suffix += 1
        return slug
