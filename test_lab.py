import tempfile, pathlib, unittest
from lab import safe_name, check_answer, get_artifact, db_init, emit
class TestLab(unittest.TestCase):
 def test_names(self):
  self.assertEqual(safe_name('note_01.txt'),'note_01.txt')
  for s in ['../escape','/tmp/x','.','a/b']:
   with self.assertRaises(ValueError):safe_name(s)
 def test_numeric(self):
  self.assertTrue(check_answer('25%','25%'))
  self.assertFalse(check_answer('12%','25%'))
 def test_paths(self):
  with tempfile.TemporaryDirectory() as d:
   base=pathlib.Path(d);path=get_artifact(base,'A01','private','memory.txt')
   self.assertTrue(str(path).startswith(d))
 def test_db(self):
  with tempfile.TemporaryDirectory() as d:
   db=db_init(pathlib.Path(d));emit(db,'A01','test',{'ok':True})
   self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
if __name__=='__main__':unittest.main()
