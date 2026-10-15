import os, sys, tempfile, unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_URL']='sqlite:///'+str(Path(tempfile.gettempdir())/'career_launchpad_tests.sqlite3')
os.environ['APP_REQUIRE_AUTH']='false'
import main
from fastapi.testclient import TestClient

class ApiTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(main.app)
    def test_health(self): self.assertEqual(self.client.get('/health').status_code,200)
    def test_auth_is_required_when_development_bypass_is_off(self):
        with patch.dict(os.environ,{'APP_REQUIRE_AUTH':'true'},clear=True):
            response=self.client.get('/api/dashboard')
        self.assertEqual(response.status_code,503)
        self.assertIn('Supabase is not configured',response.json()['detail'])
    def test_ai_missing_configuration_is_clear(self):
        old_key=os.environ.pop('NEXUS_API_KEY',None); old_model=os.environ.pop('NEXUS_MODEL',None)
        try:
            r=self.client.post('/api/mentor',json={'message':'How do I prepare?'},headers={'X-User-Id':'test-a'})
            self.assertEqual(r.status_code,503); self.assertIn('NEXUS_API_KEY',r.json()['detail'])
        finally:
            if old_key is not None: os.environ['NEXUS_API_KEY']=old_key
            if old_model is not None: os.environ['NEXUS_MODEL']=old_model
    def test_validation_and_user_scoping(self):
        self.assertEqual(self.client.post('/api/interview/start',json={'role':'x','mode':'fun'}).status_code,422)
        a=self.client.post('/api/roadmap/update',json={'task_index':0,'completed':True},headers={'X-User-Id':'user-a'})
        b=self.client.post('/api/roadmap/update',json={'task_index':0,'completed':True},headers={'X-User-Id':'user-b'})
        self.assertEqual(a.status_code,404); self.assertEqual(b.status_code,404)
    def test_file_type_validation(self):
        r=self.client.post('/api/documents',files={'file':('image.png',b'not text','image/png')},headers={'X-User-Id':'test-a'})
        self.assertEqual(r.status_code,415)
    def test_keyword_retrieval_scoped_and_no_match_truthful(self):
        with main.connect() as c:
            c.execute('INSERT INTO documents(id,user_id,filename,chunks) VALUES(?,?,?,?)',(f'doc-{__import__("uuid").uuid4()}','user-a','study.txt','["Quantum entanglement links measured particle states."]'))
        other=self.client.post('/api/documents/ask',json={'question':'quantum entanglement'},headers={'X-User-Id':'user-b'})
        self.assertEqual(other.status_code,200); self.assertFalse(other.json()['sources'])
        self.assertIn('could not find',other.json()['answer'])
    def test_resume_analysis_and_roadmap_persist_with_mocked_provider(self):
        payload={'summary':'Relevant early-career experience.','skills':['SQL'],'matching_skills':['SQL'],'missing_skills':['Experiment design'],'evidence':['Built weekly SQL reporting.'],'improvements':['Add measurable outcomes where accurate.'],'roadmap':[{'title':'Review experiment design','skill':'Experiment design','priority':'High','effort':'3 hours','completed':False}],'readiness_score':68,'score_explanation':'Indicative match based on written evidence.'}
        with patch.object(main,'completion',return_value=__import__('json').dumps(payload)):
            r=self.client.post('/api/analyze',files={'resume':('resume.txt',b'Experience: built SQL reports','text/plain')},data={'job_description':'Need SQL and experiments'},headers={'X-User-Id':'candidate-test'})
        self.assertEqual(r.status_code,200,r.text); self.assertEqual(r.json()['readiness_score'],68)
        d=self.client.get('/api/dashboard',headers={'X-User-Id':'candidate-test'})
        self.assertEqual(d.json()['roadmap'][0]['skill'],'Experiment design')
        u=self.client.post('/api/roadmap/update',json={'task_index':0,'completed':True},headers={'X-User-Id':'candidate-test'})
        self.assertTrue(u.json()['completed'])
    def test_mentor_and_interview_flows_with_mocked_provider(self):
        with patch.object(main,'completion',side_effect=['Start by clarifying the role criteria.','Tell me about a time you resolved a disagreement.','{"score":8,"strengths":["Clear example"],"improvements":["Add measurable outcome"],"missing_concepts":[],"clarity":"Easy to follow."}']):
            m=self.client.post('/api/mentor',json={'message':'How do I start?'},headers={'X-User-Id':'flow-test'})
            q=self.client.post('/api/interview/start',json={'role':'Product Analyst','mode':'HR'},headers={'X-User-Id':'flow-test'})
            f=self.client.post('/api/interview/feedback',json={'role':'Product Analyst','mode':'HR','question':q.json()['question'],'answer':'I listened and aligned on goals.'},headers={'X-User-Id':'flow-test'})
        self.assertIn('criteria',m.json()['answer']); self.assertEqual(q.status_code,200); self.assertEqual(f.json()['score'],8)
    def test_document_ingestion_and_grounded_answer(self):
        user='study-flow-'+str(__import__('uuid').uuid4())
        uploaded=self.client.post('/api/documents',files={'file':('notes.txt',b'Gradient descent adjusts model parameters to reduce the loss function.','text/plain')},headers={'X-User-Id':user})
        self.assertEqual(uploaded.status_code,200,uploaded.text)
        self.assertIn('keyword retrieval',uploaded.json()['retrieval_mode'])
        with patch.object(main,'completion',return_value='Gradient descent updates parameters to reduce loss. Source: notes.txt.'):
            answer=self.client.post('/api/documents/ask',json={'question':'How does gradient descent reduce loss?'},headers={'X-User-Id':user})
        self.assertEqual(answer.status_code,200,answer.text)
        self.assertEqual(answer.json()['sources'][0]['filename'],'notes.txt')
    def test_pdf_resume_analysis_reads_in_memory_on_windows(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, DecodedStreamObject, NameObject
        writer=PdfWriter(); page=writer.add_blank_page(width=612,height=792)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        font_ref=writer._add_object(font)
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font_ref})})
        stream=DecodedStreamObject(); stream.set_data(b'BT /F1 12 Tf 72 720 Td (Experience with Python and data analysis.) Tj ET')
        page[NameObject('/Contents')]=writer._add_object(stream)
        pdf=BytesIO(); writer.write(pdf)
        user='pdf-flow-'+str(__import__('uuid').uuid4())
        payload={'summary':'Relevant Python experience.','skills':['Python'],'matching_skills':['Python'],'missing_skills':[],'evidence':['Experience with Python.'],'improvements':[],'roadmap':[],'readiness_score':70,'score_explanation':'Indicative assessment.'}
        with patch.object(main,'completion',return_value=__import__('json').dumps(payload)):
            response=self.client.post('/api/analyze',files={'resume':('resume.pdf',pdf.getvalue(),'application/pdf')},data={'job_description':'Python analyst role'},headers={'X-User-Id':user})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['readiness_score'],70)

if __name__=='__main__': unittest.main()
