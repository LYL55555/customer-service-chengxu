import copy,json,socket,unittest
from pathlib import Path
from unittest.mock import patch
import engine
from output_contract import review_payload
from revalidation import revalidate


class SubmissionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.rows={r['case_id']:r for r in json.loads((Path(engine.ROOT)/'demo_materials/final_saved_results.json').read_text())['cases']}

    def test_saved_real_results_revalidate_without_network(self):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('offline only')):
            for identity,row in self.rows.items():
                with self.subTest(identity=identity):
                    r=revalidate(row['valid']);self.assertEqual(r['status'],'success',r.get('error'));self.assertEqual(r['result']['messages'],row['valid']['result']['messages'])
                    self.assertEqual(row['failed']['status'],'error')

    def test_single_revision_keeps_other_candidates(self):
        for identity in ['N21','N29']:
            row=self.rows[identity]
            for index in [0,2]:self.assertEqual(row['valid']['result']['messages'][index],row['failed']['parsed_output']['messages'][index])

    def test_protocol_constant_is_the_only_compatibility(self):
        q=self.rows['N39']['valid']['quality_review'];raw=q['parsed_provider_output'];contract=q['parameters']['tools'][0]['function']['parameters']
        adapted,compat=review_payload(raw,contract);self.assertEqual(adapted['source_protocol'],'sources-v4');self.assertFalse(compat['provider_native_schema_match']);self.assertNotIn('source_protocol',raw)
        for field in ['verdict','state_evidence','candidate_checks']:
            bad=copy.deepcopy(raw);bad.pop(field)
            with self.assertRaises(ValueError):review_payload(bad,contract)
        for bad in [dict(raw,source_protocol='sources-v3'),dict(raw,extra='')]:
            with self.assertRaises(ValueError):review_payload(bad,contract)

    def test_wrong_price_and_broken_reference_still_reject(self):
        r=copy.deepcopy(self.rows['N21']['valid']);r['parsed_output']['messages'][1]='轻行肩包售价19,800元。'
        self.assertEqual(revalidate(r)['status'],'error')
        r=copy.deepcopy(self.rows['N39']['valid']);r['quality_review']['parsed_output']['candidate_checks']['reply_1']['source_checks'][0]['source_id']='nonexistent'
        self.assertEqual(revalidate(r)['status'],'error')

if __name__=='__main__':unittest.main()
