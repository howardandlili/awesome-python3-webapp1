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
    #这个__pool变量我不是很理解，廖老师说是一个全局连接池，给我的感觉就像是这个池子里面已经有了一堆连接等着被取用。
    #那这堆连接的个数是多少？下面有设定最大连接数10,和最小连接数1
    #按照我的理解，刚开始应该是只有1个连接。当这一个连接被占用，刚好又有第二个数据库连接请求的时候才会创建第二个连接。
    #数据库连接用完后不会被关闭，而是储存在连接池中等待下一次被取用。
    #当有新的数据库连接请求时，会先看连接池中有没有空闲的连接，有的话就直接取用，没有才会再创建一个。
    #当连接池中连接数量达到10，连接不会再创建，估计是避免系统资源被过多的占用吧
    #而最小连接数为1,应该是为了保证刚开始一定有一个可用的数据库连接
    #以上是我个人的理解，仅供参考
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
#这个函数将来会在app.py的init函数中引用，目的是为了创建一个全局变量__pool，当需要连接数据库的时候可以直接从__pool中获取连接
#将执行sql的代码封装进select函数，调用的时候只要传入sql，和sql需要的一些参数值就好
async def select(sql, args, size=None):
    log(sql, args)
    #声明__pool是一个全局变量，这样才能引用create_pool函数创建的__pool变量
    global __pool
    async with __pool.get() as conn:#从连接池中获取一个数据库连接
        #不是很理解cur是什么，cursor翻译成中文是光标的意思，我只能猜一下了
        #上一句代码从连接池中取得数据库连接，但并没有进入到数据库中
        #conn.cursor相当于是命令行下输入mysql -uroot -p之后进入到数据库中，cur就是那个不断闪烁的光标
        #cur.execute就相当于输入sql语句，然后回车执行，个人见解仅供参考
        async with conn.cursor(aiomysql.DictCursor) as cur:
            #sql.replace的作用是把sql中的字符串占位符？换成python的占位符%s，args是执行sql语句时通过占位符插入的一些参数
            #()表示一个空的tuple，但我不太理解在这儿的作用，或者参数为空的意思？如果是这样，那为什么不在定义函数的时候直接设置args的默认值为()
            await cur.execute(sql.replace('?', '%s'), args or ())
            #size就是需要返回的结果数，如果不传入，那就默认返回所有查询结果
            if size:
                rs = await cur.fetchmany(size)
            else:
                rs = await cur.fetchall()
        #rs是查询结果，len(rs)自然就是结果数量
        logging.info('rows returned: %s' % len(rs))
        return rs
#基本上和select函数差不多，我就为不一样的地方做下注释
#autocommit是自动提交的意思，不太明白在这里有什么用
async def execute(sql,args,autocommit=True):
    # execute方法只返回结果数，不返回结果集,用于insert,update这些SQL语句
    log(sql)
    async with __pool.get() as conn:
        if not autocommit:
            #如果不是自动提交，也就是autocommit=False的话，就conn.begin()，不知道啥意思
            await conn.begin()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(sql.replace('?','%s'),args)
                affected = cur.rowcount #affected是受影响的行数，比如说插入一行数据，那受影响行数就是一行
                if not autocommit:
                    #这边同样不知道是啥意思，如果不是自动提交那就手动提交？提交什么，提交到哪儿？猜都没法猜
                    await conn.commit()
        #捕获数据库错误，但我不清楚具体是什么错误，为什么select函数不需要捕获？
        except BaseException as e:
            if not autocommit:
                #rollback是回滚的意思，那滚的是个什么玩意儿？不造啊
                await conn.rollback()
                # raise不带参数，则把此处的错误往上抛;为了方便理解还是建议加e吧
            raise e
        return affected
#这个函数在元类中被引用，作用是创建一定数量的占位符
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    #比如说num=3，那L就是['?','?','?']，通过下面这句代码返回一个字符串'?,?,?'
    return ','.join(L)
#定义字段基类，后面各种各样的字段类都继承这个基类
class Field(object):
    def __init__(self,name,column_type,primary_key,default):
        self.name = name                #字段名
        self.colum_type = column_type   #字段类型
        self.primary_key = primary_key  #主键
        self.default = default          #默认值
    #元类那节也有一个orm的例子，里面也有这个函数，好像是为了在命令行按照'<%s, %s:%s>'这个格式输出字段的相关信息
    #注释掉之后会报错，不知道什么原因，估计在哪个地方会用到这个字符串，我暂时还没找到在哪儿
    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)
#感觉这儿没什么好讲的，很简单吧，这部分内容会在models.py中引用，我会在那儿再做注释
class StringField(Field):
    #ddl是数据定义语言("data definition languages")，默认值是'varchar(100)'，意思是可变字符串，长度为100
    #和char相对应，char是固定长度，字符串长度不够会自动补齐，varchar则是多长就是多长，但最长不能超过规定长度
    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
        super().__init__(name, ddl, primary_key, default)
