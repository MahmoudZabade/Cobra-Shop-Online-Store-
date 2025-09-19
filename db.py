import pymysql

def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',         
        password='1222936',         
        database='CobraShopOnlineStore',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    ) 