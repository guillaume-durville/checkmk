# yapf: disable


checkname = 'mysql_capacity'


info = [['[[]]'],
        ['information_schema', '147456', '0'],
        ['mysql', '665902', '292'],
        ['performance_schema', '0', '0'],
        ['test', '409255936', '54525952']]


discovery = {
    '': [
        ('mysql:test', {}),
    ],
}


checks = {
    '': [
        ('mysql:test', {}, [(0, 'Size: 390.30 MB', [('database_size', 409255936, None, None, None, None)])]),
    ],
}
