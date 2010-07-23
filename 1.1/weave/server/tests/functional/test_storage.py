# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Sync Server
#
# The Initial Developer of the Original Code is the Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Tarek Ziade (tarek@mozilla.com)
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****
"""
Basic tests to verify that the dispatching mechanism works.
"""
import base64
import json
import time
import struct

from weave.server.tests.functional import support


class TestStorage(support.TestWsgiApp):

    def setUp(self):
        super(TestStorage, self).setUp()
        # user auth token
        environ = {'Authorization': 'Basic %s' % \
                        base64.encodestring('tarek:tarek')}
        self.app.extra_environ = environ

        # let's create some collections for our tests
        self.storage.set_user(1)

        for name in ('client', 'crypto', 'forms', 'history', 'col1', 'col2'):
            self.storage.set_collection(1, name)

        for item in range(3):
            self.storage.set_item(1, 'col1', item)
        for item in range(5):
            self.storage.set_item(1, 'col2', item)

    def tearDown(self):
        # removing all data after the test
        self.storage.delete_user(1)
        super(TestStorage, self).tearDown()

    def test_get_collections_info(self):

        resp = self.app.get('/1.0/tarek/info/collections')
        self.assertEquals(resp.status, '200 OK')
        res = json.loads(resp.body)
        keys = res.keys()
        keys.sort()
        # standard collections + custom ones
        wanted = ['client', 'col1', 'col2', 'crypto', 'forms', 'history']
        self.assertEquals(keys, wanted)
        self.assertEquals(int(resp.headers['X-Weave-Records']), 6)

        # XXX need to test collections timestamps here

    def test_get_collections_count(self):

        resp = self.app.get('/1.0/tarek/info/collection_counts')
        self.assertEquals(resp.status, '200 OK')
        res = json.loads(resp.body)
        self.assertEquals(res['col1'], 3)
        self.assertEquals(res['col2'], 5)
        self.assertEquals(int(resp.headers['X-Weave-Records']), 2)

    def test_get_quota(self):

        # XXX implement the new quota code
        res = self.app.get('/1.0/tarek/info/quota', status=501)
        self.assertEquals(res.status, '501 Not Implemented')

    def test_get_collection(self):
        res = self.app.get('/1.0/tarek/storage/col3')
        self.assertEquals(json.loads(res.body), [])
        resp = self.app.get('/1.0/tarek/storage/col2')
        res = json.loads(resp.body)
        ids = [line['id'] for line in res]
        ids.sort()
        self.assertEquals(ids, [0, 1, 2, 3, 4])
        self.assertEquals(int(resp.headers['X-Weave-Records']), 5)

        # trying various filters

        # "ids"
        # Returns the ids for objects in the collection that are in the
        # provided comma-separated list.
        res = self.app.get('/1.0/tarek/storage/col2?ids=1,3')
        res = json.loads(res.body)
        ids = [line['id'] for line in res]
        ids.sort()
        self.assertEquals(ids, [1, 3])

        # "predecessorid"
        # Returns the ids for objects in the collection that
        # are directly preceded by the id given. Usually only returns one
        # result.
        self.storage.set_item(1, 'col2', 125, predecessorid='XXXX')
        res = self.app.get('/1.0/tarek/storage/col2?predecessorid=XXXX')
        res = json.loads(res.body)
        ids = [line['id'] for line in res]
        ids.sort()
        self.assertEquals(ids, [125])

        # "parentid"
        # Returns the ids for objects in the collection that are the children
        # of the parent id given.
        self.storage.set_item(1, 'col2', 126, parentid='papa')
        self.storage.set_item(1, 'col2', 127, parentid='papa')
        res = self.app.get('/1.0/tarek/storage/col2?parentid=papa')
        res = json.loads(res.body)
        ids = [line['id'] for line in res]
        ids.sort()
        self.assertEquals(ids, [126, 127])

        # "older"
        # Returns only ids for objects in the collection that have been last
        # modified before the date given.
        self.storage.delete_items(1, 'col2')
        self.storage.set_item(1, 'col2', 128)
        now = time.time()
        time.sleep(0.3)
        self.storage.set_item(1, 'col2', 129)
        res = self.app.get('/1.0/tarek/storage/col2?older=%f' % now)
        res = json.loads(res.body)
        ids = [line['id'] for line in res]
        ids.sort()
        self.assertEquals(ids, [128])

        # "newer"
        # Returns only ids for objects in the collection that have been
        # last modified since the date given.
        res = self.app.get('/1.0/tarek/storage/col2?newer=%f' % now)
        res = json.loads(res.body)
        ids = [line['id'] for line in res]
        ids.sort()
        self.assertEquals(ids, [129])

        # "full"
        # If defined, returns the full WBO, rather than just the id.
        res = self.app.get('/1.0/tarek/storage/col2?full=1')
        res = json.loads(res.body)
        keys = res[0].keys()
        keys.sort()
        wanted = ['collection', 'id', 'modified', 'parentid', 'payload',
                  'payload_size', 'predecessorid', 'sortindex', 'username']
        self.assertEquals(keys, wanted)

        res = self.app.get('/1.0/tarek/storage/col2')
        res = json.loads(res.body)
        keys = res[0].keys()
        keys.sort()
        self.assertEquals(keys, ['id'])

        # "index_above"
        # If defined, only returns items with a higher sortindex than the
        # value specified.
        self.storage.set_item(1, 'col2', 130, sortindex=11)
        self.storage.set_item(1, 'col2', 131, sortindex=9)
        res = self.app.get('/1.0/tarek/storage/col2?index_above=10')
        res = json.loads(res.body)
        ids = [line['id'] for line in res]
        ids.sort()
        self.assertEquals(ids, [130])

        # "index_below"
        # If defined, only returns items with a lower sortindex than the value
        # specified.
        res = self.app.get('/1.0/tarek/storage/col2?index_below=10')
        res = json.loads(res.body)
        ids = [line['id'] for line in res]
        ids.sort()
        self.assertEquals(ids, [131])

        # "limit"
        # Sets the maximum number of ids that will be returned
        self.storage.delete_items(1, 'col2')

        for i in range(10):
            self.storage.set_item(1, 'col2', i)
        res = self.app.get('/1.0/tarek/storage/col2?limit=2')
        res = json.loads(res.body)
        self.assertEquals(len(res), 2)

        res = self.app.get('/1.0/tarek/storage/col2')
        res = json.loads(res.body)
        self.assertTrue(len(res) > 9)

        # "offset"
        # Skips the first n ids. For use with the limit parameter (required) to
        # paginate through a result set.

        # make sure we reject it if "limit" is not provided
        res = self.app.get('/1.0/tarek/storage/col2?offset=2', status=400)
        self.assertEquals(res.status_int, 400)

        # let's get 2, 3 and 4
        res = self.app.get('/1.0/tarek/storage/col2?offset=2&limit=3')
        res = json.loads(res.body)
        self.assertEquals(len(res), 3)
        ids = [line['id'] for line in res]
        ids.sort()
        self.assertEquals(ids, [2, 3, 4])

        # "sort"
        #   'oldest' - Orders by modification date (oldest first)
        #   'newest' - Orders by modification date (newest first)
        #   'index' - Orders by the sortindex descending (highest weight first)
        self.storage.delete_items(1, 'col2')

        for index, sortindex in ((0, 1), (1, 34), (2, 12)):
            self.storage.set_item(1, 'col2', index, sortindex=sortindex)

        res = self.app.get('/1.0/tarek/storage/col2?sort=oldest')
        res = json.loads(res.body)
        ids = [line['id'] for line in res]
        self.assertEquals(ids, [0, 1, 2])

        res = self.app.get('/1.0/tarek/storage/col2?sort=newest')
        res = json.loads(res.body)
        ids = [line['id'] for line in res]
        self.assertEquals(ids, [2, 1, 0])

        res = self.app.get('/1.0/tarek/storage/col2?sort=index')
        res = json.loads(res.body)
        ids = [line['id'] for line in res]
        self.assertEquals(ids, [1, 2, 0])

    def test_alternative_formats(self):

        # application/json
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(res.content_type, 'application/json')

        res = json.loads(res.body)
        ids = [line['id'] for line in res]
        ids.sort()
        self.assertEquals(ids, [0, 1, 2, 3, 4])

        # application/newlines
        res = self.app.get('/1.0/tarek/storage/col2',
                           headers=[('Accept', 'application/newlines')])
        self.assertEquals(res.content_type, 'application/newlines')

        res = [json.loads(line) for line in res.body.strip().split('\n')]
        ids = [line['id'] for line in res]
        ids.sort()
        self.assertEquals(ids, [0, 1, 2, 3, 4])

        # application/whoisi
        res = self.app.get('/1.0/tarek/storage/col2',
                           headers=[('Accept', 'application/whoisi')])
        self.assertEquals(res.content_type, 'application/whoisi')

        lines = []
        pos = current = 0
        while pos != -1:
            pos = res.body.find('\t', current)
            if pos == -1:
                break
            # getting the 32bits value
            size = res.body[pos - 3:pos + 1]
            size = struct.unpack('!I', size)[0]

            # extracting the line
            line = res.body[pos + 1:pos + size + 1]
            lines.append(json.loads(line))
            current = pos + size + 3

        ids = [line['id'] for line in lines]
        ids.sort()
        self.assertEquals(ids, [0, 1, 2, 3, 4])

        # unkown format
        res = self.app.get('/1.0/tarek/storage/col2',
                        headers=[('Accept', 'application/xxx')],
                        status=400)
        self.assertEquals(res.status_int, 400)

    def test_get_item(self):
        # grabbing object 1 from col2
        res = self.app.get('/1.0/tarek/storage/col2/1')
        res = json.loads(res.body)
        wanted = ['collection', 'id', 'modified', 'parentid', 'payload',
                  'payload_size', 'predecessorid', 'sortindex', 'username']
        keys = res.keys()
        keys.sort()
        self.assertEquals(keys, wanted)
        self.assertEquals(res['id'], 1)

        # unexisting object
        res = self.app.get('/1.0/tarek/storage/col2/99', status=404)
        self.assertEquals(res.status_int, 404)

    def test_set_item(self):
        # let's create an object
        wbo = {'payload': 'XXX', 'payload_size': 3}
        wbo = json.dumps(wbo)
        self.app.put('/1.0/tarek/storage/col2/12345', params=wbo)
        res = self.app.get('/1.0/tarek/storage/col2/12345')
        res = json.loads(res.body)
        self.assertEquals(res['payload'], 'XXX')

        # now let's update it
        wbo = {'payload': 'YYY', 'payload_size': 3}
        wbo = json.dumps(wbo)
        self.app.put('/1.0/tarek/storage/col2/12345', params=wbo)
        res = self.app.get('/1.0/tarek/storage/col2/12345')
        res = json.loads(res.body)
        self.assertEquals(res['payload'], 'YYY')

    def test_set_collection(self):
        # sending two wbos
        wbo1 = {'id': 12, 'payload': 'XXX', 'payload_size': 3}
        wbo2 = {'id': 13, 'payload': 'XXX', 'payload_size': 3}
        wbos = json.dumps([wbo1, wbo2])
        self.app.post('/1.0/tarek/storage/col2', params=wbos)

        # checking what we did
        res = self.app.get('/1.0/tarek/storage/col2/12')
        res = json.loads(res.body)
        self.assertEquals(res['payload'], 'XXX')
        res = self.app.get('/1.0/tarek/storage/col2/13')
        res = json.loads(res.body)
        self.assertEquals(res['payload'], 'XXX')

        # one more time, with changes
        wbo1 = {'id': 13, 'payload': 'XyX', 'payload_size': 3}
        wbo2 = {'id': 14, 'payload': 'XXX', 'payload_size': 3}
        wbos = json.dumps([wbo1, wbo2])
        self.app.post('/1.0/tarek/storage/col2', params=wbos)

        # checking what we did
        res = self.app.get('/1.0/tarek/storage/col2/14')
        res = json.loads(res.body)
        self.assertEquals(res['payload'], 'XXX')
        res = self.app.get('/1.0/tarek/storage/col2/13')
        res = json.loads(res.body)
        self.assertEquals(res['payload'], 'XyX')

    def test_delete_collection(self):
        self.storage.delete_items(1, 'col2')

        # creating a collection of three
        wbo1 = {'id': 12, 'payload': 'XXX', 'payload_size': 3}
        wbo2 = {'id': 13, 'payload': 'XXX', 'payload_size': 3}
        wbo3 = {'id': 14, 'payload': 'XXX', 'payload_size': 3}
        wbos = json.dumps([wbo1, wbo2, wbo3])
        self.app.post('/1.0/tarek/storage/col2', params=wbos)
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(len(json.loads(res.body)), 3)

        # deleting all items
        self.app.delete('/1.0/tarek/storage/col2')
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(len(json.loads(res.body)), 0)

        # now trying deletion with filters

        # "ids"
        # Deletes the ids for objects in the collection that are in the
        # provided comma-separated list.
        self.app.post('/1.0/tarek/storage/col2', params=wbos)
        self.app.delete('/1.0/tarek/storage/col2?ids=12,14')
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(len(json.loads(res.body)), 1)
        self.app.delete('/1.0/tarek/storage/col2?ids=13')
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(len(json.loads(res.body)), 0)

        # "parentid"
        # Only deletes objects in the collection that are the
        # children of the parent id given.
        wbo1 = {'id': 12, 'payload': 'XXX', 'payload_size': 3, 'parentid': 1}
        wbo2 = {'id': 13, 'payload': 'XXX', 'payload_size': 3, 'parentid': 1}
        wbo3 = {'id': 14, 'payload': 'XXX', 'payload_size': 3, 'parentid': 2}
        wbos = json.dumps([wbo1, wbo2, wbo3])
        self.app.post('/1.0/tarek/storage/col2', params=wbos)
        self.app.delete('/1.0/tarek/storage/col2?parentid=1')
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(len(json.loads(res.body)), 1)

        # "older"
        # Only deletes objects in the collection that have been last
        # modified before the date given
        self.app.delete('/1.0/tarek/storage/col2')
        wbo1 = {'id': 12, 'payload': 'XXX', 'payload_size': 3, 'parentid': 1}
        wbo2 = {'id': 13, 'payload': 'XXX', 'payload_size': 3, 'parentid': 1}
        wbos = json.dumps([wbo1, wbo2])
        self.app.post('/1.0/tarek/storage/col2', params=wbos)

        now = time.time()
        time.sleep(.3)
        wbo3 = {'id': 14, 'payload': 'XXX', 'payload_size': 3, 'parentid': 2}
        wbos = json.dumps([wbo3])
        self.app.post('/1.0/tarek/storage/col2', params=wbos)

        self.app.delete('/1.0/tarek/storage/col2?older=%f' % now)
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(len(json.loads(res.body)), 1)

        # "newer"
        # Only deletes objects in the collection that have been last modified
        # since the date given.
        self.app.delete('/1.0/tarek/storage/col2')
        wbo1 = {'id': 12, 'payload': 'XXX', 'payload_size': 3, 'parentid': 1}
        wbo2 = {'id': 13, 'payload': 'XXX', 'payload_size': 3, 'parentid': 1}
        wbos = json.dumps([wbo1, wbo2])
        self.app.post('/1.0/tarek/storage/col2', params=wbos)

        now = time.time()
        time.sleep(.3)
        wbo3 = {'id': 14, 'payload': 'XXX', 'payload_size': 3, 'parentid': 2}
        wbos = json.dumps([wbo3])
        self.app.post('/1.0/tarek/storage/col2', params=wbos)

        self.app.delete('/1.0/tarek/storage/col2?newer=%f' % now)
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(len(json.loads(res.body)), 2)

        # "limit"
        # Sets the maximum number of objects that will be deleted.
        # xxx see how to activate this under sqlite

        #self.app.delete('/1.0/tarek/storage/col2')
        #wbos = json.dumps([wbo1, wbo2, wbo3])
        #self.app.post('/1.0/tarek/storage/col2', params=wbos)
        #self.app.delete('/1.0/tarek/storage/col2?limit=2')
        #res = self.app.get('/1.0/tarek/storage/col2')
        #self.assertEquals(len(json.loads(res.body)), 1)

        # "sort"
        #   'oldest' - Orders by modification date (oldest first)
        #   'newest' - Orders by modification date (newest first)
        #   'index' - Orders by the sortindex (ordered lists)
        #   'depthindex' - Orders by depth, then by sortindex (ordered trees)

        # sort is used only if limit is used.
        # check this with toby

    def test_delete_item(self):
        self.storage.delete_items(1, 'col2')

        # creating a collection of three
        wbo1 = {'id': 12, 'payload': 'XXX', 'payload_size': 3}
        wbo2 = {'id': 13, 'payload': 'XXX', 'payload_size': 3}
        wbo3 = {'id': 14, 'payload': 'XXX', 'payload_size': 3}
        wbos = json.dumps([wbo1, wbo2, wbo3])
        self.app.post('/1.0/tarek/storage/col2', params=wbos)
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(len(json.loads(res.body)), 3)

        # deleting item 13
        self.app.delete('/1.0/tarek/storage/col2/13')
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(len(json.loads(res.body)), 2)

        # unexisting item
        res = self.app.delete('/1.0/tarek/storage/col2/12982', status=404)
        self.assertEquals(res.status_int, 404)

    def test_delete_storage(self):
        self.storage.delete_items(1, 'col2')

        # creating a collection of three
        wbo1 = {'id': 12, 'payload': 'XXX', 'payload_size': 3}
        wbo2 = {'id': 13, 'payload': 'XXX', 'payload_size': 3}
        wbo3 = {'id': 14, 'payload': 'XXX', 'payload_size': 3}
        wbos = json.dumps([wbo1, wbo2, wbo3])
        self.app.post('/1.0/tarek/storage/col2', params=wbos)
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(len(json.loads(res.body)), 3)

        # deleting all with no confirmation
        res = self.app.delete('/1.0/tarek/storage', status=400)
        self.assertEquals(res.status_int, 400)

        # deleting all for real now
        res = self.app.delete('/1.0/tarek/storage/col2',
                              headers=[('X-Confirm-Delete', '1')])
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertEquals(len(json.loads(res.body)), 0)

    def test_x_weave_timestamp(self):
        res = self.app.get('/1.0/tarek/storage/col2')
        self.assertTrue(time.time() -
                        float(res.headers['X-Weave-Timestamp']) > 0)

        # getting the timestamp with a PUT
        wbo = {'payload': 'XXX', 'payload_size': 3}
        wbo = json.dumps(wbo)
        res = self.app.put('/1.0/tarek/storage/col2/12345', params=wbo)
        self.assertTrue(time.time() -
                        float(res.headers['X-Weave-Timestamp']) > 0)

        # getting the timestamp with a POST
        wbo1 = {'id': 12, 'payload': 'XXX', 'payload_size': 3}
        wbo2 = {'id': 13, 'payload': 'XXX', 'payload_size': 3}
        wbos = json.dumps([wbo1, wbo2])
        res = self.app.post('/1.0/tarek/storage/col2', params=wbos)
        self.assertTrue(time.time() -
                        float(res.headers['X-Weave-Timestamp']) > 0)
