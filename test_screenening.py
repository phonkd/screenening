import unittest
from screenening import load_models, make_profiles

Monitor, Profile, _ = load_models()


class LayoutTests(unittest.TestCase):
    def monitors(self):
        return [Monitor(name='eDP-1', description='Laptop', width=1920, height=1200),
                Monitor(name='DP-1', description='Left', width=2560, height=1440),
                Monitor(name='DP-2', description='Right', width=2560, height=1440)]

    def test_dock_and_solo(self):
        solo, dock = make_profiles(self.monitors(), 'DP-1')
        self.assertEqual([(m.x, m.y) for m in dock.monitors], [(1600, 1440), (0, 0), (2560, 0)])
        self.assertEqual([r.monitor for r in dock.workspace_rules],
                         ['desc:Laptop'] * 3 + ['desc:Left'] * 3 + ['desc:Right'] * 3)
        self.assertEqual([r.monitor for r in solo.workspace_rules], ['desc:Laptop'] * 9)
        self.assertEqual(Profile.from_dict(dock.to_dict()).to_dict(), dock.to_dict())
        for profile in (solo, dock):
            for monitor in profile.monitors:
                self.assertEqual(monitor.to_dict()['resolution_mode'], 'highrr')
                self.assertIn('mode = highrr', monitor.to_hyprland_v2_block())

    def test_scaled_rotated_and_swap(self):
        from monique.models import Transform
        monitors = self.monitors()
        monitors[1].scale = 2
        monitors[2].transform = Transform(1)
        _, dock = make_profiles(monitors, 'DP-2')
        laptop, left, right = dock.monitors
        self.assertEqual((left.x, left.y), (0, 0))
        self.assertEqual((right.x, right.y), (1440, 1840))
        self.assertEqual((laptop.x, laptop.y), (400, 2560))

    def test_solo_and_invalid(self):
        monitors = self.monitors()
        self.assertEqual(len(make_profiles(monitors[:1])[0].workspace_rules), 9)
        with self.assertRaises(RuntimeError):
            make_profiles(monitors[:2])
        monitors[2].description = 'Left'
        with self.assertRaises(RuntimeError):
            make_profiles(monitors, 'DP-1')


if __name__ == '__main__':
    unittest.main()
