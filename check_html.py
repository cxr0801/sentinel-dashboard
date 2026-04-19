import re

with open(r'sentinel_dashboard.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find the POSTS block
m = re.search(r'const POSTS=\[(.*?)\];', html, flags=re.DOTALL)
if m:
    posts_block = m.group(1)
    print('Posts block length:', len(posts_block))
    # Check for raw newlines  
    lines = posts_block.split('\n')
    in_string = False
    for lno, line in enumerate(lines):
        quotes = line.count('"') - line.count('\\"')
        if quotes % 2 != 0:
            in_string = not in_string
        if in_string and lno > 0:
            print(f'Line {lno}: raw newline inside string -> {repr(line[:60])}')
else:
    print('POSTS block not found')
