import pandas as pd
from trajcenter.core.trajectory import Trajectory, TrajectoryMeta, ExternalAxisConfig

def test_save_load_roundtrip():
    df = pd.DataFrame({
        'x': [100.0, 200.0], 'y': [150.0, 250.0], 'z': [50.0, 60.0],
        'q1': [1.0, 1.0], 'q2': [0.0, 0.0], 'q3': [0.0, 0.0], 'q4': [0.0, 0.0],
        'eax_a': [45.0, 90.0],
    })
    meta = TrajectoryMeta(
        name='test_pointage',
        robot_model='IRB6700',
        external_axes={
            'eax_a': ExternalAxisConfig(
                axis_type='rotational', unit='deg', label='Positionneur A'
            )
        }
    )
    traj = Trajectory(meta=meta, points=df)
    path = traj.save('trajectory_store/test.trajcenter')

    traj2 = Trajectory.load(path)
    assert traj2.point_count == 2
    assert traj2.meta.name == 'test_pointage'
    assert 'eax_a' in traj2.active_external_axes
    print(traj2)
test_save_load_roundtrip()