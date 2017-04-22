#!/user/bin/env python
# -*- coding:utf-8 -*-
__authoer__ = 'Howie'

import asyncio,logging # 支持异步IO,日志操作
import aiomysql,pdb # 异步mysql驱动支持

def log(sql,args=()):
    # 该函数用于打印执行的SQL语句
    logging.INFO('SQL: %s' % sql)

#创建连接池
@asyncio.coroutine
def create_pool(loop,**kw): # 引入关键字后不用显示import asyncio了
    # 该函数用于创建连接池
    global __pool # 全局变量用于保存连接池
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host','10.88.1.108'),  # 默认定义host名字为localhost,主机是什么
        port=kw.get('port','3306'),         #端口
        user=kw('user'),                    # user是通过关键字参数传进来的
        password=kw('password'),            # 密码也是通过关键字参数传进来的
        db=kw('db'),                        # 数据库名字，如果做ORM测试的使用请使用db=kw['db']
        charset=kw.get('charset','utf8'),   # 默认数据库字符集是utf8
        aotocommit=kw.get('autocommit',True),# 默认自动提交事务
        maxsize=kw.get('maxsize',10),       # 连接池最多同时处理10个请求
        minsize=kw.get('minsize',1),        # 连接池最少1个请求
        loop=loop                           # 传递消息循环对象loop用于异步执行
    )
# =============================SQL处理函数区==========================
# select和execute方法是实现其他Model类中SQL语句都经常要用的方法，原本是全局函数，这里作为静态函数处理
# 注意：之所以放在Model类里面作为静态函数处理是为了更好的功能内聚，便于维护，这点与廖老师的处理方式不同，请注意
@asyncio.coroutine
def select(sql,args,size=None):
    # select语句则对应该select方法,传入sql语句和参数
    log(sql,args)
    global __pool # 这里声明global,是为了区分赋值给同名的局部变量(这里其实可以省略，因为后面没赋值)
    # with语句用法可以参考我的博客：http://kaimingwan.com/post/python/pythonzhong-de-withyu-ju-shi-yong

    # 异步等待连接池对象返回可以连接线程，with语句则封装了清理（关闭conn）和处理异常的工作
    with(yield from __pool) as conn:
        # 等待连接对象返回DictCursor可以通过dict的方式获取数据库对象，需要通过游标对象执行SQL
        cur = yield from conn.cursor(aiomysql.DictCursor)
        # 所有args都通过repalce方法把占位符替换成%s
        # args是execute方法的