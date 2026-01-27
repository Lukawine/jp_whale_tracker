mock_announcements = [
    {
        'title': '7203: 业绩修正に関するお知らせ (Notice of Earnings Revision)',
        'url': 'https://example.com/tdnet/7203_earnings_revision.pdf', # Mock PDF URL
        'stock_code': '7203',
        'date': '2026-01-26T10:00:00'
    },
    {
        'title': '9984: 株式報酬制度に関するお知らせ (Notice regarding stock compensation system)',
        'url': 'https://example.com/tdnet/9984_stock_compensation.html', # Mock HTML URL
        'stock_code': '9984',
        'date': '2026-01-26T10:15:00'
    },
    {
        'title': '7203: 自己株式の取得に関するお知らせ (Notice of Share Repurchase)',
        'url': 'https://example.com/tdnet/7203_share_repurchase.xbrl', # Mock XBRL URL
        'stock_code': '7203',
        'date': '2026-01-26T10:30:00'
    },
    {
        'title': '1234: 通常の発表 (Normal Announcement)',
        'url': 'https://example.com/tdnet/1234_normal.pdf', # Irrelevant, should be filtered out
        'stock_code': '1234',
        'date': '2026-01-26T10:45:00'
    },
    {
        'title': '9984: 大量売出に関するお知らせ (Notice of Large-scale Sale)',
        'url': 'https://example.com/tdnet/9984_large_sale.xbrl', # Mock XBRL URL
        'stock_code': '9984',
        'date': '2026-01-26T11:00:00'
    },
]
