import psycopg2

try:
    conn = psycopg2.connect(dbname='insightloop', user='user', password='pass', host='127.0.0.1', port=5432)
    cur = conn.cursor()
    cur.execute('SELECT 1')
    print('psycopg connected', cur.fetchone())
    cur.close()
    conn.close()
except Exception as e:
    print('psycopg error', type(e).__name__, e)
