import unittest
from assemble_candidate import verify_report
class AssemblyGate(unittest.TestCase):
    def test_rejects_failed_runtime(self):
        with self.assertRaises(ValueError):verify_report({'pass':False},{})
    def test_rejects_empty_claim_of_success(self):
        with self.assertRaises(ValueError):verify_report({'pass':True,'checks':{}},{})
if __name__=='__main__':unittest.main()
