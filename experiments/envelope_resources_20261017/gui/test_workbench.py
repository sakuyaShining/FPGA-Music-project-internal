import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QPA_FONTDIR','C:/Windows/Fonts')
import tempfile
import time
import unittest
from unittest.mock import patch
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
import dsp_host as dh
from serial_link import SimLink, SerialLink
from instrument_config import default_config
from device_config import apply_supported
from live_visualizer import LiveWorker, LiveAnalysis
from test_live_visualizer import frame
from workbench import WorkbenchWindow


class StreamingPort:
    """Protocol fixture only; generated silence is never product audio."""
    timeout=.5
    def __init__(self, wrong_identity=False):
        self.regs={0x7f:0x11,0xa4:0 if wrong_identity else 0xd4,0xa5:4,0xa9:32,
                   0:7,0x37:2,0x40:1,0x5a:0}
        self.pending=b'';self.streaming=False;self.closed=False
        self.ops=[];self.seq=0;self.stamp=0
    @property
    def in_waiting(self):return len(self.pending)
    def reset_input_buffer(self):self.pending=b''
    def write(self,data):
        self.ops.append(bytes(data))
        for i in range(0,len(data),2):
            a,d=data[i:i+2]
            if a==15:
                assert not self.streaming
                self.pending+=bytes((d,self.regs.get(d,0)))
            elif a==0xb5:self.streaming=bool(d)
            else:self.regs[a]=d
        return len(data)
    def read(self,n):
        if not self.pending and self.streaming:
            time.sleep(.004)
            self.pending=frame(seq=self.seq,stamp=self.stamp,fmt=2)
            self.seq=(self.seq+1)&65535;self.stamp+=2048
        raw=self.pending[:n];self.pending=self.pending[n:]
        return raw
    def flush(self):pass
    def close(self):self.closed=True

class SilentPort(StreamingPort):
    def read(self,n):
        self.pending=b''
        return b''


class AdapterTests(unittest.TestCase):
    def test_disk_full_export_preserves_previous_evidence(self):
        from pathlib import Path
        from types import SimpleNamespace
        from evidence_export import EvidenceWorker
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'evidence.json';target.write_text('previous')
            worker=EvidenceWorker(str(target),dict(status='FAILED'))
            messages=[];worker.result.connect(messages.append)
            with patch('evidence_export.shutil.disk_usage',return_value=SimpleNamespace(free=0)):
                worker.run()
            self.assertEqual(target.read_text(),'previous')
            self.assertIn('失败',messages[0])
    def model(self):
        link=SimLink();link.regs[0x7f]=0x11;return link

    def test_partial_application_preserves_ctrl_and_does_not_refresh(self):
        link=self.model();link.regs[0]=6
        doc=default_config();doc['preset']=2
        r=apply_supported(link,doc)
        self.assertEqual(r['status'],'PARTIAL_PARAMETER_CONFIRMED')
        self.assertEqual(r['readback']['CTRL'],14)
        self.assertTrue(r['unsupported']);self.assertFalse(r['audio_verified'])
        self.assertNotIn(0x63,[a for a,_,_ in r['writes']])
        self.assertEqual(sum(a==0x59 for a,_,_ in r['writes']),16)

    def test_unsupported_protocol_never_writes(self):
        link=self.model();link.regs[0x7f]=0x10
        with patch.object(link,'send') as send:
            self.assertEqual(apply_supported(link,default_config())['status'],'FAILED')
            send.assert_not_called()

    def test_short_write_and_bad_readback_fail(self):
        for broken in ('send','readback'):
            link=self.model()
            if broken=='send':link.send=lambda f:1
            else:
                original=link.read_reg
                link.read_reg=lambda a: 99 if a==0x37 else original(a)
            result=apply_supported(link,default_config())
            self.assertEqual(result['status'],'FAILED');self.assertTrue(result['writes'])

    def test_preset_application_clears_additional_spectrum(self):
        r=apply_supported(self.model(),default_config(),True)
        self.assertEqual([d for a,d,_ in r['writes'] if a==0x59],[0]*16)
        self.assertEqual(r['readback']['SPEC_MODE'],0)

    def test_live_scheduler_drains_before_configuration_and_restarts(self):
        link=SerialLink('TEST',460800)
        link.kind='真实串口'
        worker=LiveWorker(link)
        class Port:
            timeout=.5
            def __init__(self):
                self.regs={0x7f:0x11,0xa4:0xd4,0xa5:4,0xa9:32,0:0,0x37:0,0x5a:0}
                self.pending=b'';self.streaming=False;self.starts=0;self.ops=[]
                self.fragmented_tail=[]
            @property
            def in_waiting(self):return len(self.pending)
            def reset_input_buffer(self):self.pending=b''
            def write(self,data):
                self.ops.append(bytes(data))
                for i in range(0,len(data),2):
                    a,d=data[i:i+2]
                    if a==15:
                        assert not self.streaming
                        self.pending+=bytes((d,self.regs.get(d,0)))
                    elif a==0xb5:
                        self.streaming=bool(d)
                        if d:
                            self.starts+=1
                            self.pending+=frame(seq=self.starts-1,stamp=(self.starts-1)*4096,fmt=2)
                        elif self.starts==1:
                            tail=frame(seq=1,stamp=2048,fmt=2)
                            self.fragmented_tail=[tail[:70],b'',tail[70:]]
                    else:self.regs[a]=d
                return len(data)
            def flush(self):pass
            def read(self,n):
                if self.fragmented_tail:
                    time.sleep(.01)
                    return self.fragmented_tail.pop(0)
                raw=self.pending[:n];self.pending=self.pending[n:]
                if self.streaming and raw:
                    if self.starts==1 and worker.commands.empty():worker.configure(default_config())
                    elif self.starts==2:worker.stop()
                return raw
        link.ser=Port();records=[];gaps=[]
        worker.configuration.connect(records.append);worker.observation_gap.connect(lambda:gaps.append(1))
        worker.run()
        self.assertEqual(records[0]['status'],'PARTIAL_PARAMETER_CONFIRMED')
        self.assertEqual(gaps,[1]);self.assertEqual(link.ser.starts,2)
        self.assertFalse(link.capture_busy)
        self.assertEqual(link.ser.timeout,.5)
        self.assertTrue(link._transaction.acquire(False));link._transaction.release()

    def test_explicit_gap_clears_fft_and_does_not_join_samples(self):
        model=LiveAnalysis();model.audio=[1,2];model.expected=100;model.active[60]=1
        model.mark_gap();self.assertEqual(len(model.audio),0)
        self.assertIsNone(model.expected);self.assertFalse(model.active)


class WorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.w=WorkbenchWindow(self.temp.name+'/display.json')
        self.w.link=SimLink();self.w.link.regs[0x7f]=0x11
        self.w.show();self.app.processEvents();self.w.timer.stop()
    def tearDown(self):
        self.w.editor._saved=self.w.editor.document()
        self.w.editor_panel.saved=self.w.editor_panel.document()
        self.w.close();self.w.deleteLater();self.app.processEvents();self.temp.cleanup()
    def test_navigation_preserves_held_notes_and_observation(self):
        self.w.note_on(0);model=self.w.audio_page.live_model
        for i in (1,2,3,0):
            self.w.pages.setCurrentIndex(i);self.app.processEvents()
            self.assertEqual(self.w.held,{0:60})
            self.assertIs(self.w.audio_page.live_model,model)
            self.assertTrue(self.w.audio_page.isVisible())
        self.w._shift_octave(1);self.w.note_off(0)
        self.assertEqual(self.w.held,{})
        self.assertEqual(self.w.journal[-2][1],60)
    def test_simple_surface_hides_development_controls(self):
        self.assertFalse(self.w.pages.isVisible())
        self.assertFalse(self.w.advanced_dialog.isVisible())
        self.assertFalse(self.w.sound_panel.isVisible())
        self.w.edit_toggle.setChecked(True);self.app.processEvents()
        self.assertTrue(self.w.sound_panel.isVisible())
        self.assertFalse(self.w.pages.isVisible())
    def test_drawn_sound_is_explicit_and_waits_for_release(self):
        self.w.select_performance_preset(4)
        self.w.editor_panel.name.setText('手绘测试')
        self.w.editor_panel.bars.set_values([200,100]+[0]*14)
        self.assertIsNone(self.w.apply_worker)
        self.w.note_on(0)
        self.w.editor_panel.use.click()
        self.assertFalse(self.w.applying)
        self.assertIsNotNone(self.w.pending_sound)
        self.w.note_off(0);self.w._apply_pending_preset()
        self.w.apply_worker.wait(1000);self.app.processEvents()
        record=self.w.device_record
        self.assertEqual(record['readback']['PRESET'],0)
        self.assertEqual(record['readback']['SPEC_MODE'],1)
        self.assertEqual([d for a,d,_ in record['writes'] if a==0x59],[200,100]+[0]*14)
        self.assertEqual(self.w.performance_preset.currentIndex(),4)
        self.assertIn('手绘测试',self.w.device_status.text())
    def test_input_field_typing_never_starts_notes(self):
        self.w.editor.name.setFocus();QTest.keyClicks(self.w.editor.name,'zxcm')
        self.assertFalse(self.w.held)
    def test_mouse_and_keyboard_overlap_has_one_note_until_both_release(self):
        self.w.note_on(0,'keyboard');self.w.note_on(0,'mouse')
        self.assertEqual(len(self.w.journal),2)
        self.w.note_off(0,'mouse');self.assertEqual(self.w.held,{0:60})
        self.w.note_off(0,'keyboard');self.assertFalse(self.w.held)
        self.assertEqual(len(self.w.journal),4)
    def test_piano_sends_every_semitone_and_high_c(self):
        from piano_keyboard import INDEX
        self.w.journal=[]
        for offset in range(25):
            button=self.w.piano.buttons[INDEX[offset]]
            QTest.mousePress(button,Qt.LeftButton)
            self.assertEqual(self.w.held,{INDEX[offset]:60+offset})
            self.assertTrue(button.isDown())
            QTest.mouseRelease(button,Qt.LeftButton)
            self.assertFalse(self.w.held)
            self.assertFalse(button.isDown())
        self.assertEqual([d for a,d,_ in self.w.journal if a==0x60],
            [value for offset in range(25) for value in (128+60+offset,60+offset)])
    def test_fast_repeated_key_presses_send_every_on_off_pair(self):
        self.w.setFocus();self.app.processEvents();self.w.journal=[]
        for _ in range(20):
            QTest.keyPress(self.w,Qt.Key_Z)
            QTest.keyRelease(self.w,Qt.Key_Z)
        self.assertEqual([d for a,d,_ in self.w.journal if a==0x60],[188,60]*20)
        self.assertFalse(self.w.held)
        self.assertFalse(self.w.input_sources)
    def test_piano_black_keys_overlay_white_keys_at_small_size(self):
        from piano_keyboard import INDEX, BLACK
        from PyQt5.QtCore import QPoint
        self.w.resize(776,558);self.app.processEvents()
        piano=self.w.piano
        for offset in range(25):
            button=piano.buttons[INDEX[offset]]
            self.assertIs(piano.childAt(button.geometry().center()),button)
            self.assertLessEqual(button.geometry().right(),piano.width())
            if offset%12 not in BLACK:
                bottom=QPoint(button.geometry().center().x(),piano.height()-5)
                self.assertIs(piano.childAt(bottom),button)
    def test_piano_keyboard_aliases_and_mouse_release_independently(self):
        from piano_keyboard import INDEX
        index=INDEX[12]
        self.w.setFocus();self.app.processEvents()
        QTest.keyPress(self.w,Qt.Key_Q)
        self.assertEqual(self.w.held,{index:72})
        QTest.keyPress(self.w,Qt.Key_Comma)
        self.w.note_on(index,'mouse')
        self.assertEqual(len(self.w.input_sources[index]),3)
        QTest.keyRelease(self.w,Qt.Key_Q)
        self.assertEqual(self.w.held,{index:72})
        QTest.keyRelease(self.w,Qt.Key_Comma)
        self.assertEqual(self.w.held,{index:72})
        self.w.note_off(index,'mouse')
        self.assertFalse(self.w.held)
        self.assertEqual(sum(a==0x60 for a,_,_ in self.w.journal),2)
    def test_piano_black_key_chord_release_survives_octave_change(self):
        self.w.setFocus();self.app.processEvents()
        QTest.keyPress(self.w,Qt.Key_S)
        QTest.keyPress(self.w,Qt.Key_7)
        self.assertEqual(sorted(self.w.held.values()),[61,82])
        self.w._shift_octave(1)
        QTest.keyRelease(self.w,Qt.Key_S)
        QTest.keyRelease(self.w,Qt.Key_7)
        self.assertFalse(self.w.held)
        self.assertEqual([d for a,d,_ in self.w.journal if a==0x60],[189,210,61,82])
    def test_piano_octave_limits_cover_c2_to_c8(self):
        from piano_keyboard import INDEX
        self.w._shift_octave(-100)
        self.assertFalse(self.w.audio_page.oct_down.isEnabled())
        self.w.note_on(INDEX[0]);self.w.note_off(INDEX[0])
        self.w._shift_octave(100)
        self.assertFalse(self.w.audio_page.oct_up.isEnabled())
        self.w.note_on(INDEX[24]);self.w.note_off(INDEX[24])
        self.assertEqual([d for a,d,_ in self.w.journal if a==0x60],[164,36,236,108])
    def test_piano_shortcuts_do_not_play_when_typing_or_using_control(self):
        self.w.setFocus();self.app.processEvents()
        QTest.keyPress(self.w,Qt.Key_S,Qt.ControlModifier)
        self.assertFalse(self.w.held)
        QTest.keyRelease(self.w,Qt.Key_S,Qt.ControlModifier)
        self.w.edit_toggle.setChecked(True)
        self.w.editor_panel.name.setFocus()
        QTest.keyClicks(self.w.editor_panel.name,'s2qz')
        self.assertFalse(self.w.held)
    def test_piano_drag_releases_previous_note_and_focus_loss_releases_all(self):
        from PyQt5.QtGui import QMouseEvent
        from PyQt5.QtCore import QEvent, QPointF
        from piano_keyboard import INDEX
        piano=self.w.piano;first=piano.buttons[INDEX[0]];black=piano.buttons[INDEX[1]]
        QTest.mousePress(first,Qt.LeftButton)
        point=black.mapToGlobal(black.rect().center())
        move=QMouseEvent(QEvent.MouseMove,QPointF(first.mapFromGlobal(point)),
            QPointF(point),Qt.NoButton,Qt.LeftButton,Qt.NoModifier)
        QApplication.sendEvent(first,move)
        self.assertEqual(self.w.held,{INDEX[1]:61})
        self.w._release_keys()
        self.assertFalse(self.w.held)
        self.assertFalse(self.w.input_sources)
        self.assertIsNone(piano.mouse_note)
        QTest.mouseRelease(first,Qt.LeftButton)
        self.assertFalse(self.w.held)
    def test_application_is_async_and_draft_is_unchanged(self):
        before=self.w.editor.document();self.w.apply_draft(True)
        self.assertTrue(self.w.applying)
        self.w.apply_worker.wait(1000);self.app.processEvents()
        self.assertFalse(self.w.applying)
        self.assertEqual(self.w.editor.document(),before)
        self.assertEqual(self.w.device_record['status'],'PARTIAL_PARAMETER_CONFIRMED')
    def test_performance_preset_uses_real_preset_instead_of_default_replace_sine(self):
        draft=self.w.editor.document()
        self.assertEqual(draft['spectrum_mode'],'replace')
        self.w.select_performance_preset(2)
        self.w.apply_worker.wait(1000);self.app.processEvents()
        self.assertEqual(self.w.device_record['readback']['PRESET'],2)
        self.assertEqual(self.w.device_record['readback']['SPEC_MODE'],0)
        self.assertEqual([d for a,d,_ in self.w.device_record['writes'] if a==0x59],[0]*16)
        self.assertEqual(self.w.editor.document(),draft)
        self.assertIn('当前音色',self.w.device_status.text())
    def test_preset_switch_while_held_waits_for_release_without_retrigger(self):
        self.w.note_on(4);self.w.select_performance_preset(1)
        self.assertFalse(self.w.applying);self.assertEqual(self.w.pending_preset,1)
        self.assertEqual(self.w.held,{4:69})
        self.w.note_off(4);self.w._apply_pending_preset()
        self.w.apply_worker.wait(1000);self.app.processEvents()
        self.assertEqual(self.w.device_record['readback']['PRESET'],1)
        self.assertEqual(sum(a==0x60 for a,_,_ in self.w.journal),2)
        self.assertNotIn(0x63,[a for a,_,_ in self.w.journal])
    def test_in_play_application_is_refused_and_release_remains_available(self):
        self.w.note_on(0);self.w.apply_draft()
        self.assertFalse(self.w.applying)
        self.w.applying=True;self.w.note_off(0);self.assertFalse(self.w.held)
        self.w.applying=False
    def test_simulation_cannot_pass_audio_test(self):
        self.w.start_test();self.assertFalse(self.w.testing);self.assertFalse(self.w.test_records)
    def test_default_spectrum_keeps_updating_and_freeze_is_explicit(self):
        import numpy as np
        from live_visualizer import FrameParser,FS
        m=self.w.audio_page.live_model;p=FrameParser()
        self.assertFalse(self.w.onset_hold.isChecked());self.assertFalse(m.hold_onset)
        def feed(hz,seq,stamp):
            x=(np.sin(np.arange(1024)*2*np.pi*hz/(FS/4))*6000).astype('<i2')
            raw=frame(seq=seq,stamp=stamp,fmt=2,payload=x[:512].tobytes())+frame(seq=seq+1,stamp=stamp+2048,fmt=2,payload=x[512:].tobytes())
            m.ingest(dict(frames=p.feed(raw),crc_errors=0,gaps=0))
            self.w.audio_page.refresh_live()
            return m.frequencies[np.argmax(m.db)]
        first=feed(440,0,0);second=feed(880,2,4096)
        self.assertLess(abs(first-440),FS/4/1024)
        self.assertLess(abs(second-880),FS/4/1024)
        self.assertGreater(second,first*1.8)
        self.w.onset_hold.setChecked(True);self.assertTrue(m.hold_onset)
        self.assertEqual(len(m.db),0)  # No accepted onset: cannot fake a frozen view.
        self.w.onset_hold.setChecked(False);self.assertFalse(m.hold_onset)
        self.assertLess(abs(m.frequencies[np.argmax(m.db)]-880),FS/4/1024)
    def test_missing_acceptance_events_cannot_pass_measurement(self):
        import numpy as np
        self.w.testing=True
        model=self.w.audio_page.live_model;model.sample_rate=13183.59375
        self.w.test_health=(0,0,0,0)
        self.w.test_events=[];self.w.test_wire=[]
        x=(np.sin(np.arange(4096)*2*np.pi*440/model.sample_rate)*2000).astype(np.int16)
        self.w.test_sustain=x;self.w.test_audio=[x]
        self.w._finish_test()
        self.assertEqual(self.w.test_records[-1]['status'],'FAILED_OR_INCONCLUSIVE')
        self.assertFalse(self.w.test_records[-1]['timbre_verified'])
    def test_abort_only_releases_owned_note(self):
        self.w.testing=True;self.w.journal=[]
        self.w.abort_test()
        self.assertEqual([a for a,_,_ in self.w.journal],[0x60,0x61])
        self.assertEqual(self.w.journal[0][1],69)
    def test_720p_keeps_keys_and_three_views_visible(self):
        self.w.resize(1280,720);self.app.processEvents()
        self.assertEqual(self.w.height(),720)
        for widget in (self.w.audio_page.trajectory,self.w.audio_page.live_wave,
                       self.w.audio_page.live_spectrum,self.w.audio_page.play_buttons[-1]):
            self.assertTrue(widget.isVisible());self.assertGreater(widget.width(),30)
            self.assertLess(widget.mapTo(self.w,widget.rect().bottomRight()).y(),720)

    def wait_until(self,predicate):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            self.app.processEvents()
            if predicate():return
            QTest.qWait(10)
        self.fail('异步连接/流状态未在限时内完成')

    def connect_fixture(self,wrong_identity=False,protocol_flag=0x11):
        self.w.link=None
        self.w.cmb_port.addItem('TEST');self.w.cmb_port.setCurrentText('TEST')
        port=StreamingPort(wrong_identity)
        port.regs[0x7f]=protocol_flag
        def open_link(link):
            link.ser=port;link.kind='真实串口';link.detail='TEST @ 460800';return True
        with patch.object(SerialLink,'open',open_link):self.w._toggle_conn()
        return port

    def test_connection_automatically_streams_and_enters_performance(self):
        port=self.connect_fixture()
        try:
            self.wait_until(lambda:self.w.performance_ready)
            self.assertIn(b'\xb5\x01',port.ops)
            self.assertEqual(port.regs[0],14)  # Disable test, retain expressions.
            self.assertIn('可以演奏',self.w.device_status.text())
            self.assertFalse(self.w.audio_page.live_button.isVisible())
            QTest.keyPress(self.w,Qt.Key_Z);self.assertEqual(self.w.held,{0:60})
            QTest.keyRelease(self.w,Qt.Key_Z);self.assertFalse(self.w.held)
            self.w._toggle_conn()  # Single click stops stream AND closes port.
            self.wait_until(lambda:self.w.link is None)
            self.assertTrue(port.closed)
            self.assertIn(b'\xb5\x00',port.ops)
        finally:
            if self.w.live_worker.isRunning():
                self.w.live_worker.stop();self.w.live_worker.wait(2000);self.app.processEvents()

    def test_score_uses_background_stream_owner_and_stop_remains_available(self):
        port=self.connect_fixture()
        try:
            self.wait_until(lambda:self.w.performance_ready)
            self.w.ed_score.setText('60:1,62:1,64:1')
            started=time.monotonic();self.w.seq_play()
            self.assertLess(time.monotonic()-started,.1)
            self.wait_until(lambda:not self.w.sequence_busy)
            self.assertEqual(self.w.sequence_record['status'],'CONFIRMED')
            self.assertTrue(self.w.sequence_playing)
            self.assertEqual(port.regs[0x73],3)
            self.assertTrue(port.streaming)
            self.w.note_on(0);self.assertFalse(self.w.held)
            self.w._performance_panic()
            self.wait_until(lambda:not self.w.sequence_playing and not self.w.sequence_busy)
            self.assertEqual(port.regs[0x50],0)
            self.w._toggle_conn();self.wait_until(lambda:self.w.link is None)
        finally:
            if self.w.live_worker.isRunning():
                self.w.live_worker.stop();self.w.live_worker.wait(2000);self.app.processEvents()

    def test_stop_during_score_download_is_queued_instead_of_ignored(self):
        self.w.ed_score.setText('60:1,62:1')
        self.w.seq_play();self.w.seq_stop()
        self.wait_until(lambda:not self.w.sequence_busy and not self.w.pending_sequence_stop)
        self.assertFalse(self.w.sequence_playing)
        self.assertEqual(self.w.link.regs[0x50],0)

    def test_bad_identity_never_streams_or_enables_playing(self):
        port=self.connect_fixture(True)
        self.wait_until(lambda:not self.w.live_worker.isRunning())
        self.app.processEvents()
        self.assertFalse(self.w.performance_ready)
        self.assertNotIn(b'\xb5\x01',port.ops)
        self.w.note_on(0);self.assertFalse(self.w.held)
        self.assertIn('连接未就绪',self.w.device_status.text())

    def test_mutable_protocol_flag_does_not_override_fixed_live_capabilities(self):
        port=self.connect_fixture(protocol_flag=15)
        try:
            self.wait_until(lambda:self.w.performance_ready)
            self.assertEqual(port.regs[0x7f],15)
            self.assertIn('协议标志异常',self.w.device_status.text())
            self.w.apply_draft(True)
            self.wait_until(lambda:not self.w.applying)
            self.assertEqual(self.w.device_record['status'],'PARTIAL_PARAMETER_CONFIRMED')
            self.assertTrue(self.w.device_record['warnings'])
            self.assertEqual(port.regs[0x7f],15)
            self.w._toggle_conn();self.wait_until(lambda:self.w.link is None)
        finally:
            if self.w.live_worker.isRunning():
                self.w.live_worker.stop();self.w.live_worker.wait(2000);self.app.processEvents()

    def test_full_view_at_small_window_and_editor_does_not_hide_plots(self):
        self.assertFalse(self.w.pages.isVisible())
        self.w.resize(1024,640);self.app.processEvents()
        self.assertEqual(self.w.size().width(),1024)
        self.assertEqual(self.w.size().height(),640)
        self.assertGreater(self.w.audio_page.width(),950)
        self.w.resize(1280,720);self.w.edit_toggle.setChecked(True);self.app.processEvents()
        self.assertTrue(self.w.sound_panel.isVisible())
        self.assertTrue(self.w.audio_page.live_wave.isVisible())
        self.assertGreater(self.w.audio_page.live_wave.width(),250)
    def test_unresponsive_board_has_actionable_message_not_wrong_identity(self):
        link=SerialLink('TEST',460800);link.ser=SilentPort()
        worker=LiveWorker(link,prepare_performance=True);messages=[]
        worker.failure.connect(messages.append);worker.run()
        self.assertIn('设备未响应',messages[0])
        self.assertIn('已开机',messages[0])
        self.assertFalse(link.capture_busy)
        self.assertNotIn(b'\xb5\x01',link.ser.ops)


if __name__=='__main__':unittest.main()
