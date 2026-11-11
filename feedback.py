"""Editorial evidence from aggregate counts; never consumes user identities.
Run: python3 feedback.py < /private/path/aggregate.json
First run python3 build.py. Input is SELECT * FROM public.editorial_feedback.
Output goes to stdout, not the public site or git. Similarity is judged by the
editor using title/summary/section, not by a brittle keyword blacklist.
"""
import json
from pathlib import Path
import sys


def evidence(rows, catalog):
    result = []
    for row in rows:
        item = catalog.get(row['item_id'])
        if not item:  # Ignore unknown IDs, including forged IDs and removed items.
            continue
        likes, dislikes = row['likes'], row['dislikes']
        if any(type(n) is not int or n < 0 for n in (likes, dislikes)):
            raise ValueError('Counts must be nonnegative integers')
        total = likes + dislikes
        # Symmetric prior shrinks sparse feedback towards neutral.
        score = (likes - dislikes) / (total + 6)
        signal = 'neutral'
        if total >= 5 and dislikes / total >= 2 / 3:
            signal = 'avoid_similar'
        elif total >= 5 and likes / total >= 2 / 3:
            signal = 'prefer_similar'
        result.append({**item, 'likes': likes, 'dislikes': dislikes,
                       'votes': total, 'interest_score': round(score, 4), 'signal': signal})
    return sorted(result, key=lambda item: (item['interest_score'], -item['votes'], item['id']))


if __name__ == '__main__':
    catalog = json.loads((Path(__file__).parent / 'dist/items.json').read_text())
    print(json.dumps(evidence(json.load(sys.stdin), catalog), ensure_ascii=False, indent=2))
