import motor.motor_asyncio
client = motor.motor_asyncio.AsyncIOMotorClient()


async def setup_db():
    db = AsyncIOMotorClient().test
    await db.pages.drop()
    html = '<html><body>{}</body></html>'
    await db.pages.insert_one({'_id': 'page-one',
                               'body': html.format('Hello!')})

    await db.pages.insert_one({'_id': 'page-two',
                               'body': html.format('Goodbye.')})

    return db


async def do_insert():
    db = client()['test_database']
    collection = db['test_collection']
    document = {'key': 'value'}
    result = await db.test_collection.insert_one(document)
    print('result %s' % repr(result.inserted_id))
    return {result}
