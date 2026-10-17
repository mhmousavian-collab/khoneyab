from fastapi.testclient import TestClient
from app.main import app


def test_health_and_meta_endpoints():
    with TestClient(app) as client:
        health = client.get('/api/health')
        meta = client.get('/api/meta')
        assert health.status_code == 200
        assert health.json()['status'] == 'ok'
        assert health.json()['advertisements'] >= 150
        assert meta.status_code == 200
        assert len(meta.json()['cities']) >= 8
        assert meta.json()['synthetic_data'] is True


def test_interpret_search_detail_and_compare_flow():
    with TestClient(app) as client:
        interpreted = client.post('/api/search/interpret', json={
            'query': 'آپارتمان دو خوابه برای خرید در تهران تا ۱۵ میلیارد تومان، نزدیک مترو و دارای پارکینگ'
        })
        assert interpreted.status_code == 200
        criteria = interpreted.json()['criteria']
        assert criteria['bedrooms'] == 2
        assert criteria['max_price_toman'] == 15_000_000_000
        results = client.post('/api/search', json={'criteria': criteria, 'sort_by': 'relevance', 'limit': 10})
        assert results.status_code == 200
        payload = results.json()
        assert payload['total'] >= 1
        assert all(row['city'] == 'تهران' and row['transaction_type'] == 'sale' for row in payload['results'])
        property_id = payload['results'][0]['property_id']
        detail = client.get(f'/api/properties/{property_id}')
        assert detail.status_code == 200
        assert detail.json()['synthetic'] is True
        ids = [p['property_id'] for p in payload['results'][:2]]
        compare = client.get('/api/compare', params={'ids': ','.join(ids)})
        assert compare.status_code == 200
        assert len(compare.json()['properties']) == 2


def test_rent_filter_and_empty_strict_results():
    with TestClient(app) as client:
        rent = client.post('/api/search', json={'criteria': {
            'transaction_type': 'rent', 'city': 'مشهد', 'bedrooms': 2,
            'must_have_amenities': ['parking'], 'preferred_amenities': [], 'emphasis': []
        }})
        assert rent.status_code == 200
        assert all(p['transaction_type'] == 'rent' and p['city'] == 'مشهد' and p['parking'] for p in rent.json()['results'])
        empty = client.post('/api/search', json={'criteria': {
            'transaction_type': 'sale', 'city': 'تهران', 'max_price_toman': 1,
            'must_have_amenities': [], 'preferred_amenities': [], 'emphasis': []
        }})
        assert empty.status_code == 200
        assert empty.json()['results'] == []
        assert empty.json()['near_matches']
