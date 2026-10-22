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
                self.assertEqual(monitor.to_dict()['resolution_mode'], 'explicit')
                self.assertIn(f'mode = {monitor.width}x{monitor.height}@',
                              monitor.to_hyprland_v2_block())

    def test_resolution_upgrade_uses_selected_dimensions(self):
        monitors = self.monitors()
        for monitor in monitors[1:]:
            monitor.width, monitor.height = 1920, 1080
            monitor.available_modes = ['1920x1080@100.00Hz', '2560x1440@60Hz',
                                       '2560x1440@99.95Hz']
        solo, dock = make_profiles(monitors, 'DP-1')
        self.assertEqual([(m.x, m.y) for m in dock.monitors],
                         [(1600, 1440), (0, 0), (2560, 0)])
        for monitor in dock.monitors[1:]:
            self.assertEqual((monitor.width, monitor.height, monitor.refresh_rate),
                             (2560, 1440, 99.95))
            block = monitor.to_hyprland_v2_block()
            self.assertIn('mode = 2560x1440@99.95', block)
            self.assertIn(f'position = {monitor.x}x{monitor.y}', block)
        restored = Profile.from_dict(dock.to_dict())
        self.assertEqual(restored.to_dict(), dock.to_dict())
        self.assertEqual(monitors[1].width, 1920)

    def test_laptop_upgrade_applies_to_solo_and_dock(self):
        monitors = self.monitors()
        monitors[0].available_modes = ['2560x1600@60Hz']
        solo, dock = make_profiles(monitors, 'DP-1')
        self.assertEqual((solo.monitors[0].width, solo.monitors[0].height), (2560, 1600))
        self.assertEqual((solo.monitors[0].x, solo.monitors[0].y), (0, 0))
        self.assertEqual((dock.monitors[0].x, dock.monitors[0].y), (1280, 1440))

    def test_upgrade_scaled_rotated_swapped_and_fractional(self):
        from monique.models import Transform
        monitors = self.monitors()
        for monitor in monitors[1:]:
            monitor.width, monitor.height = 1920, 1080
            monitor.available_modes = ['2560x1440@99']
        monitors[1].scale = 2
        monitors[2].transform = Transform(1)
        _, dock = make_profiles(monitors, 'DP-2')
        self.assertEqual([(m.x, m.y) for m in dock.monitors],
                         [(400, 2560), (0, 0), (1440, 1840)])
        monitors[2].scale = 1.3
        _, dock = make_profiles(monitors, 'DP-2')
        laptop, left, right = dock.monitors
        self.assertGreaterEqual(right.x, left.x + left.logical_width)
        for monitor in (left, right):
            self.assertGreaterEqual(laptop.y, monitor.y + monitor.logical_height)

    def test_unparseable_modes_fail(self):
        monitors = self.monitors()
        monitors[1].available_modes = ['invalid']
        with self.assertRaisesRegex(RuntimeError, 'DP-1'):
            make_profiles(monitors, 'DP-1')

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
