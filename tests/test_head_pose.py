import json
import math
from pathlib import Path
import tempfile
import unittest
import numpy as np
from eyecheck.head_pose import extract, reference, relative
from eyecheck.gaze_model import fit, estimate, inputs, load_profile, balanced_weights
from eyecheck.collection import schedule, Protocol
from test_collection import observation
import test_collection

def pose(yaw=0, pitch=0, roll=0):
    y,p,r = map(math.radians, (yaw,pitch,roll))
    rx=np.array([[1,0,0],[0,math.cos(p),-math.sin(p)],[0,math.sin(p),math.cos(p)]])
    ry=np.array([[math.cos(y),0,math.sin(y)],[0,1,0],[-math.sin(y),0,math.cos(y)]])
    rz=np.array([[math.cos(r),-math.sin(r),0],[math.sin(r),math.cos(r),0],[0,0,1]])
    m=np.eye(4); m[:3,:3]=rz@ry@rx
    return extract(m, {'eye_midpoint_x':.5,'eye_midpoint_y':.5,'interocular_width_fraction':.2})

class HeadPoseTests(unittest.TestCase):
    def test_offline_training_evaluation_and_leakage_guards(self):
        import hashlib
        from types import SimpleNamespace
        from eyecheck.gaze_model import dispatch, dataset
        from eyecheck.collection import fit_anchors
        cal=fit_anchors(test_collection.CalibrationTests().anchors())
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            def session(name,split,sitting):
                p=root/name;p.mkdir()
                rows=[]
                for i in range(30):
                    x=.2+.02*i;y=.3+.01*i
                    row={'gaze_eligible':True,'role':'gaze_target','attempt_id':1,'condition':'natural',
                         'relative_pose':[0,0,0,0,0,0],'target_normalized':[x,y],
                         'observation':observation(2*x+1,3*y-2)}
                    row['observation']['eyes']['right'].update(iris_x=4*x-1,iris_y=2*y+2)
                    rows.append(row)
                (p/'observations.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
                (p/'events.jsonl').write_text('',encoding='utf-8')
                m={'session_id':name,'protocol':'eyecheck-head-pose-v2','split':split,'status':'recorded','sitting_id':sitting,
                   'model_sha256':'synthetic','actual_frame_size':[1920,1080],'feature_schema':'synthetic',
                   'display':{'window_logical_size':[1920,1080]},
                   'summary':{'completed':True,'calibration':cal,'attempts':[{'id':1,'status':'recorded'}]},
                   'file_sha256':{n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ('events.jsonl','observations.jsonl')}}
                (p/'manifest.json').write_text(json.dumps(m),encoding='utf-8')
                return str(p)
            a=session('a','train','sitting1');b=session('b','train','sitting2');c=session('c','test','sitting3')
            profile=root/'profile.json'
            dispatch(SimpleNamespace(command='train-gaze',sessions=[a,b],out=profile,alpha=.01))
            out=root/'results.json'
            dispatch(SimpleNamespace(command='evaluate-gaze',sessions=[c],out=out,profile=profile,split='test'))
            self.assertEqual(json.loads(out.read_text())['conditions']['natural']['joint_coverage_of_eligible'],1)
            d=session('d','test','sitting1')
            with self.assertRaises(ValueError):
                dispatch(SimpleNamespace(command='evaluate-gaze',sessions=[d],out=root/'bad.json',profile=profile,split='test'))
            with self.assertRaises(ValueError): dataset([a,a],'train')
            with open(Path(a)/'observations.jsonl','a') as f:f.write('{}\n')
            with self.assertRaises(ValueError):dataset([a],'train')

    def test_smoothing_resets_after_invalid_or_stale_data(self):
        from eyecheck.gaze_model import Smoother
        s=Smoother()
        s.update({'valid':True,'gaze':[0,0]},1)
        p=s.update({'valid':True,'gaze':[1,1]},1.05)
        self.assertTrue(0<p['gaze'][0]<1)
        s.update(None,1.1)
        self.assertEqual(s.update({'valid':True,'gaze':[1,1]},1.15)['gaze'],[1,1])

    def test_axes_and_relative_rotation(self):
        p=pose(12, -6, 4)
        np.testing.assert_allclose([p[k] for k in ('yaw','pitch','roll')], [12,-6,4], atol=1e-10)
        ref=reference([p]*20)
        np.testing.assert_allclose(relative(p,ref), np.zeros(6), atol=1e-10)
        self.assertAlmostEqual(relative(pose(8),reference([pose()]*20))[0],8)

    def test_missing_reflection_and_unstable_reference(self):
        self.assertFalse(extract(None,{})['valid'])
        m=np.eye(4); m[0,0]=-1
        self.assertFalse(extract(m,{})['valid'])
        with self.assertRaises(ValueError): reference([pose(-8)]*10+[pose(8)]*10)

    def test_pose_campaign_keeps_one_calibration_and_separate_reference(self):
        steps=schedule(1,head_pose=True)
        self.assertEqual(steps[0].role,'pose_reference')
        self.assertEqual(sum(s.role=='calibration_anchor' for s in steps),4)
        self.assertEqual(sum(s.condition=='fixation_head_motion' for s in steps),9)
        self.assertEqual(sum(s.role=='gaze_target' for s in steps),113)
        self.assertEqual([s.role for s in schedule(1,head_pose=True,tracking=True)], ['pose_reference']+['calibration_anchor']*4+['calibration_check','tracking'])

    def test_campaign_reference_and_anchor_pose_gates(self):
        p=Protocol(schedule(4,trials=1,reading_seconds=10,head_pose=True),head_pose=True)
        now=1.; p.advance(now)
        while not p.completed:
            p.painted(p.version,now,{})
            now+=2.001; p.tick(now); p.painted(p.version,now,{})
            for i in range(25):
                t=now+.01+i*.04
                o=observation(*p.step.target,closed=p.step.label=='closed')
                o['head_pose']=pose()
                p.observation(t,t+.01,o)
            now+=p.step.seconds+.001; p.tick(now)
            self.assertNotEqual(p.state,'retry')
            if p.state=='review': p.advance(now,'no_command' if p.step.role=='negative_reading' else p.step.label)
        self.assertIsNotNone(p.pose_reference)
        self.assertEqual(len(p.calibration['eyes']),2)

    def test_residual_model_learns_head_effect_and_abstains(self):
        from eyecheck.collection import fit_anchors, predict
        cal=fit_anchors(test_collection.CalibrationTests().anchors())
        rng=np.random.default_rng(6)
        x=rng.normal(size=(300,10)); target=rng.normal(size=(300,2))
        base=target-np.column_stack((.02*x[:,4],-.03*x[:,5]))
        model=fit(x,target,base,np.ones(300),1e-8)
        correction=np.column_stack(((x-model['mean'])/model['scale'],np.ones(300)))@model['coefficients']
        np.testing.assert_allclose(base+correction,target,atol=1e-7)
        result=estimate(model,cal,[2,-.5,1,3],[100,0,0,0,0,0])
        self.assertFalse(result['valid'])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'model.json'; path.write_text(json.dumps(model))
            self.assertEqual(load_profile(path)['schema'],model['schema'])
            model['scale'][0]=0; path.write_text(json.dumps(model))
            with self.assertRaises(ValueError):load_profile(path)

    def test_fixation_balance_prevents_long_trial_dominating(self):
        rows=[{'sitting':'a','session':'a','attempt':1}]*10+[{'sitting':'a','session':'a','attempt':2}]
        w=balanced_weights(rows)
        self.assertAlmostEqual(sum(w[:10]),w[-1])
