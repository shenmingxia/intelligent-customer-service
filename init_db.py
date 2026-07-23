import sqlite3
import os

# 确保 data 目录存在
os.makedirs('data', exist_ok=True)

conn = sqlite3.connect('data/orders.db')
c = conn.cursor()

c.execute('DROP TABLE IF EXISTS orders')

c.execute('''
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    user_id TEXT,
    status TEXT,
    tracking_company TEXT,
    tracking_number TEXT,
    estimated_delivery TEXT,
    amount REAL,
    refund_status TEXT,
    refundable INTEGER,
    refund_tip TEXT
)
''')

c.execute('''
INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', ('Z100001', 'web-user', '已发货', '顺丰速运', 'SF000001', '明天 18:00 前', 128.5, '未申请退款', 1, '可提交售后申请。'))

c.execute('''
INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', ('Z100002', 'other-user', '已签收', '中通快递', 'ZT000002', '今天 10:30 已签收', 89.9, '可申请退货', 1, '可提交退货退款申请。'))

conn.commit()
conn.close()
print("数据库初始化完成")