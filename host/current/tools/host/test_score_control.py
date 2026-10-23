import unittest
from unittest.mock import patch
from serial_link import SimLink
from score_control import apply_sequence


class ScoreTests(unittest.TestCase):
    def test_download_does_not_start_and_play_enable_is_last(self):
        link=SimLink();notes=[(60,1),(0,1),(64,2)]
        for play in (False,True):
            result=apply_sequence(link,notes,120,play)
            self.assertEqual(result['status'],'CONFIRMED')
            self.assertEqual(result['readback'],dict(SEQ_CTRL=int(play),SCORE_LEN=3,TEMPO_INC=636))
            writes=result['writes']
            self.assertEqual(writes[0][:2],(0x50,0))
            if play:self.assertEqual(writes[-1][:2],(0x50,1))
    def test_invalid_score_cannot_stop_or_partially_overwrite_a_song(self):
        link=SimLink()
        with patch.object(link,'send') as send:
            self.assertEqual(apply_sequence(link,[(60,0)],120,True)['status'],'FAILED')
            send.assert_not_called()
    def test_stop_and_bad_readback(self):
        link=SimLink()
        self.assertEqual(apply_sequence(link)['status'],'CONFIRMED')
        with patch.object(link,'read_reg',return_value=7):
            result=apply_sequence(link,[(60,1)],120,True)
            self.assertEqual(result['status'],'FAILED')
            self.assertTrue(result['sent_complete'])
    def test_multibyte_writes_follow_actual_consecutive_register_addresses(self):
        import dsp_host as dh
        frames=dh.Frames();frames.w24('TEMPO',0x123456);frames.w16('VIB_DEPTH',0xabcd)
        self.assertEqual([(a,d) for a,d,_ in frames.items],
            [(0x51,0x56),(0x52,0x34),(0x53,0x12),(0x33,0xcd),(0x34,0xab)])
