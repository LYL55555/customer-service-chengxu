import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import app
from workspace_store import WorkspaceStore


class WorkbenchExamplesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);(self.root/'data').mkdir();self.ws=WorkspaceStore(self.root/'data/workspace.sqlite3')
        self.advisor=self.ws.create('advisor',dict(name='测试工作台'))['id'];tree=self.ws.create('customer',dict(name='虚构客户',advisor_id=self.advisor));self.customer=tree['id'];self.conversation=next(r['id']for r in tree['conversations']if r['customer_id']==self.customer)
        for key,value in [('ROOT',self.root),('WORKSPACE',self.ws)]:p=patch.object(app,key,value);p.start();self.addCleanup(p.stop)

    def manifest(self,customer=None):
        (self.root/'data/submission_demo.json').write_text(json.dumps(dict(advisor_id=self.advisor,sessions=[dict(case_id='N29',customer_id=customer or self.customer,conversation_id=self.conversation)])))

    def test_no_registry_does_not_guess_examples_by_name(self):self.assertEqual(app.saved_examples(),[])

    def test_explicit_registered_owner_and_conversation(self):
        self.manifest();rows=app.saved_examples();self.assertEqual(len(rows),1);self.assertEqual(rows[0]['customer_id'],self.customer);self.assertEqual(rows[0]['label'],'拉链售后处理')

    def test_other_customer_cannot_be_mapped_by_same_name(self):
        other=self.ws.create('customer',dict(name='虚构客户',advisor_id=self.advisor))['id'];self.manifest(other);self.assertEqual(app.saved_examples(),[])

if __name__=='__main__':unittest.main()
