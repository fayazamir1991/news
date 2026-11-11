import unittest
from feedback import evidence
import build


class Feedback(unittest.TestCase):
    def test_sparse_balanced_and_majority(self):
        catalog = {k: {'id': k, 'title': k, 'summary': 'tracking', 'section': 'research'} for k in 'abcde'}
        rows = [dict(item_id=k, likes=l, dislikes=d) for k,l,d in [('a',0,1),('b',1,5),('c',8,2),('d',5,5),('e',0,0),('unknown',0,99)]]
        values = {r['id']:r for r in evidence(rows,catalog)}
        self.assertEqual(len(values),5)
        self.assertEqual(values['a']['signal'],'neutral')
        self.assertEqual(values['b']['signal'],'avoid_similar')
        self.assertEqual(values['c']['signal'],'prefer_similar')
        self.assertEqual(values['d']['signal'],'neutral')
        self.assertEqual(values['e']['interest_score'],0)
        self.assertGreater(values['a']['interest_score'],-1)
        with self.assertRaises(ValueError): evidence([dict(item_id='a',likes=-1,dislikes=1)],catalog)

    def test_all_published_cards_and_surveys_have_shared_controls(self):
        build.build()
        import json
        catalog = json.loads((build.OUT / 'items.json').read_text())
        for path in (build.OUT / 'issues').glob('*/index.html'):
            text = path.read_text()
            self.assertEqual(text.count('class="reaction"'), 2*text.count('class="bookmark"'))
        for path in (build.OUT / 'surveys').glob('*/index.html'):
            text = path.read_text()
            self.assertEqual(text.count('class="reaction"'),2)
            self.assertTrue(any(f'data-item-id="{k}"' in text for k in catalog))
