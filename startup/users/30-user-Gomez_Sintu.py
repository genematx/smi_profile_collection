def run_saxs_nexafs_sintu(t=1):
    proposal_id('2021_1', '307896_Katz1')
    yield from nexafs_prep_multisample_matt(t=0.5)
    yield from bps.sleep(10)
    
    proposal_id('2021_1', '307808_Gomez3')
    yield from nexafs_prep_multisample_sintu(t=0.5)
    
    proposal_id('2021_1', '307896_Katz1')
    yield from saxs_prep_multisample_matt(t=0.5)

    proposal_id('2021_1', '307808_Gomez3')
    yield from saxs_prep_multisample_sintu(t=0.5)



def saxs_prep_multisample_matt(t=1):
    yield from bps.mv(GV7.open_cmd, 1 )
    yield from bps.mv(att2_9.open_cmd, 1)
    yield from bps.mv(att2_10.open_cmd, 1)
    dets = [pil300KW, pil1M]

    energies = [4030, 4040, 4050, 4055, 4075]
    det_exposure_time(t,t) 
    name_fmt = '{sample}_{energy}eV_pos{posi}_wa{wa}_xbpm{xbpm}'
    waxs_range = [0, 6.5, 13.0, 19.5, 26, 32.5, 39.0]
    det_exposure_time(t,t)

    for wa in waxs_range[::-1]:
        yield from bps.mv(waxs, wa)
        yield from bps.mv(stage.y, 0)
        yield from bps.mv(stage.th, 0)

        samples = ['sampleCaAc_Hyd', 'sample04', 'sample03', 'sample02', 'sample01', 'sampleCaSuDh']
        x_list  = [            4000,      14000,      24000,      34000,      42300,          56500]
        y_list =  [             550,        550,        800,        800,       1050,           5300]
        z_list =  [            1700,       1700,       1700,       1700,       1700,           1700]

        for name, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(piezo.y, y)
            yield from bps.mv(piezo.z, z)

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.mv(piezo.y, y + (k+1)*50)

                name_fmt = '{sample}_{energy}eV_xbpm{xbpm}_wa{wa}'

                sample_name = name_fmt.format(sample=name, energy=e, xbpm = '%3.1f'%xbpm3.sumY.value, wa='%2.1f'%wa)
                sample_id(user_name='OS', sample_name=sample_name)
                print(f'\n\t=== Sample: {sample_name} ===\n')
                yield from bp.count(dets, num=1)
                            
            yield from bps.mv(energy, 4050)
            yield from bps.mv(energy, 4030)

    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)


def nexafs_prep_multisample_matt(t=1):   

    yield from bps.mv(stage.y, 0)
    yield from bps.mv(stage.th, 0)

    samples = ['sampleCaAc_Hyd', 'sample04', 'sample03', 'sample02', 'sample01', 'sampleCaSuDh']
    x_list  = [            4000,      14000,      24000,      34000,      42300,          56500]
    y_list =  [             550,        550,        800,        800,       1050,           5300]
    z_list =  [            1700,       1700,       1700,       1700,       1700,           1700]

    for name, x, y, z in zip(samples, x_list, y_list, z_list):
        yield from bps.mv(piezo.x, x)
        yield from bps.mv(piezo.y, y)
        yield from bps.mv(piezo.z, z)
        yield from NEXAFS_Ca_edge_multi_sintu(t=t, name=name)

    sample_id(user_name='test', sample_name='test')


def nexafs_prep_multisample_sintu(t=1):

    yield from bps.mv(stage.th, 2.5)
    yield from bps.mv(stage.y, -10)

    # samples = ['O2_1', 'O2_2', 'O2_3', 'O2_4', 'O2_5', 'O5_1', 'O5_2']
    # x_list  = [ 43500,  33500,  23500,  12500,   3500,  -9500, -18800]
    # y_list =  [ -9250,  -9250,  -9250,  -9250,  -9250,  -9250,  -9250]
    # z_list =  [  4400,   4000,   4000,   4000,   4000,   4000,   4000]

    # samples = ['N1_1', 'N1_2', 'N1_3', 'N1_4', 'N2_1', 'N2_2', 'N2_3', 'N2_4', 'N3_1', 'N3_2', 'N3_3', 'N4_1', 'N4_2', 'N4_3', 'N5_1',
    # 'N5_2', 'N5_3']
    # x_list  = [ 46000, 42100, 38900, 35400, 30300, 27000, 23600, 19100,  8400,  3800,  -600, -8600, -13500, -18900, -27900, -34500, -40500]
    # y_list =  [ -9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000,  -9000,  -9000,  -9000,  -9500,  -9000]
    # z_list =  [  3500,  3500,  3500,  3500,  3500,  3500,  3500,  3500,  3500,  3500,  3500,  3500,   3500,   3500,   3500,   3500,   3500]


    samples = ['R1_1', 'R2_1', 'R3_1', 'R4_1', 'R5_1']
    x_list  = [ 46500,  26500,   5600, -12000, -31500]
    y_list =  [ -8000,   -8000,  -8000,  -8000,  -8000]
    z_list =  [  3500,    3500,   3500,   3500,   3500]


    for name, x, ysss, z in zip(samples, x_list, y_list, z_list):
        yield from bps.mv(piezo.x, x)
        yield from bps.mv(piezo.y, ysss)
        yield from bps.mv(piezo.z, z)
        yield from NEXAFS_Ca_edge_multi_sintu(t=t, name=name)
    

    # yield from bps.mv(stage.y, 0)
    # yield from bps.mv(stage.th, 0)

    # samples = ['O5_3', 'O5_4', 'O8_1', 'O8_2', 'O8_3', 'O8_4', 'O8_5', 'O11_1', 'O11_2',  'O11_3', 'O11_4']
    # x_list  = [ 44000,  36000,  26000,  15700,  12700,  -1300,  -8300,  -23300,  -30300,  -36300,   -44300]
    # y_list =  [ -1250,  -1250,  -1250,  -1000,  -1250,  -1250,  -1250,   -1250,   -1250,   -1250,    -1250]
    # z_list =  [  2700,   2700,   2700,   2700,   2700,   2700,   2700,    2700,    2700,    3200,     3500]

    # samples = ['P1_1', 'P1_2', 'P1_3', 'P2_1', 'P2_2', 'P2_3', 'P3_1', 'P3_2', 'P3_3', 'P4_1', 'P4_2', 'P4_3', 'P5_1', 'P5_2', 'P5_3',
    # 'P6_1', 'P6_2', 'P6_3', 'P7_1', 'P7_2', 'P7_3', 'P8_1', 'P8_2', 'P8_3']
    # x_list  = [ 45000, 40700, 37100, 32000, 29000, 25500, 19800, 16300, 12700, 6400, 3300, -200, -5000, -8800, -12400, -17600, -21000, 
    # -24500, -29800, -33500, -36600, -40350, -42950, -45500]
    # y_list =  [  -750,  -750,  -750,  -750,  -750,  -750,  -750,  -750,  -750, -750, -750, -750,  -750,  -750,   -750,   -750,   -750,
    #     -750,   -750,   -750,   -750,   -750,   -750,   -650]
    # z_list =  [  2700,  2800,  2900,  3000,  3100,  3200,  3200,  3200,  3300, 3300, 3400, 3400,  3500,  3500,   3600,   3600,   3700,
    #     3700,   3800,   3800,   3900,   3900,   4000,   4000]

    # samples = ['P1_1', 'P2_1', 'P3_1', 'P4_1', 'P5_1', 'P6_1', 'P7_1', 'P8_1']
    # x_list  = [ 45000,  32000,  19800,   6400,  -5000, -17600, -29800, -40350]
    # y_list =  [  -750,   -750,   -750,   -750,   -750,   -750,   -750,   -750]
    # z_list =  [  2700,   3000,   3200,   3300,   3500,   3600,   3800,   3900]

    # for name, x, y, z in zip(samples, x_list, y_list, z_list):
    #     yield from bps.mv(piezo.x, x)
    #     yield from bps.mv(piezo.y, y)
    #     yield from bps.mv(piezo.z, z)
    #     yield from NEXAFS_Ca_edge_multi_sintu(t=t, name=name)

    sample_id(user_name='test', sample_name='test')



def saxs_prep_multisample_sintu(t=1):
    yield from bps.mv(GV7.open_cmd, 1 )
    yield from bps.mv(att2_9.open_cmd, 1)
    yield from bps.mv(att2_10.open_cmd, 1)

    dets = [pil300KW, pil1M]

    energies = [4030, 4040, 4050, 4055, 4065, 4075, 4105]
    det_exposure_time(t,t) 
    name_fmt = '{sample}_{energy}eV_pos{posi}_wa{wa}_xbpm{xbpm}'
    waxs_range = [0, 6.5, 13.0, 19.5]


    det_exposure_time(t,t)

    ypos = [0, 400, 3]    
    for wa in waxs_range[::-1]:
        yield from bps.mv(waxs, wa)
        yield from bps.mv(stage.th, 2.5)
        yield from bps.mv(stage.y, -10)

        # samples = ['O2_1', 'O2_2', 'O2_3', 'O2_4', 'O2_5', 'O5_1', 'O5_2']
        # x_list  = [ 43500,  33500,  23500,  12500,   3500,  -9500, -18800]
        # y_list =  [ -9250,  -9250,  -9250,  -9250,  -9250,  -9250,  -9250]
        # z_list =  [  4400,   4000,   4000,   4000,   4000,   4000,   4000]

        # samples = ['N1_1', 'N1_2', 'N1_3', 'N1_4', 'N2_1', 'N2_2', 'N2_3', 'N2_4', 'N3_1', 'N3_2', 'N3_3', 'N4_1', 'N4_2', 'N4_3', 'N5_1',
        # 'N5_2', 'N5_3']
        # x_list  = [ 46000, 42100, 38900, 35400, 30300, 27000, 23600, 19100,  8400,  3800,  -600, -8600, -13500, -18900, -27900, -34500, -40500]
        # y_list =  [ -9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000,  -9000,  -9000,  -9000,  -9500,  -9000]
        # z_list =  [  3500,  3500,  3500,  3500,  3500,  3500,  3500,  3500,  3500,  3500,  3500,  3500,   3500,   3500,   3500,   3500,   3500]


        samples = ['R1_1', 'R1_2', 'R1_3', 'R2_1', 'R2_2', 'R2_3', 'R3_1', 'R3_2', 'R3_3', 'R4_1', 'R4_2', 'R4_3', 'R5_1', 'R5_2', 'R5_3']
        x_list  = [ 46500,  42000,  36500,  26500,  20500,  14000,   5600,      0,  -6100, -12000, -19000, -26000, -31500, -36500, -41700]
        y_list =  [ -8000,  -8000,  -8000,  -8000,  -8000,  -8000,  -8000,  -8000,  -8000,  -8000,  -8000,  -8000,  -8000,  -8500,  -8000]
        z_list =  [  3500,   3500,   3500,   3500,   3500,   3500,   3500,   3500,   3500,   3500,   3500,   3500,   3500,   3500,   3500]


        for name, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(piezo.y, y+100)
            yield from bps.mv(piezo.z, z)

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.sleep(1)
                name_fmt = '{sample}_{energy}eV_xbpm{xbpm}_wa{wa}'

                sample_name = name_fmt.format(sample=name, energy=e, xbpm = '%3.1f'%xbpm3.sumY.value, wa='%2.1f'%wa)
                sample_id(user_name='SR', sample_name=sample_name)
                print(f'\n\t=== Sample: {sample_name} ===\n')
                yield from bp.rel_scan(dets, piezo.y, *ypos)
                            

            yield from bps.mv(energy, 4050)
            yield from bps.sleep(1)
            yield from bps.mv(energy, 4030)

        yield from bps.mv(stage.y, 0)
        yield from bps.mv(stage.th, 0)

        # samples = ['O5_3', 'O5_4', 'O8_1', 'O8_2', 'O8_3', 'O8_4', 'O8_5', 'O11_1', 'O11_2',  'O11_3', 'O11_4']
        # x_list  = [ 44000,  36000,  26000,  15700,  12700,  -1300,  -8300,  -23300,  -30300,  -36300,   -44300]
        # y_list =  [ -1250,  -1250,  -1250,  -1000,  -1250,  -1250,  -1250,   -1250,   -1250,   -1250,    -1250]
        # z_list =  [  2700,   2700,   2700,   2700,   2700,   2700,   2700,    2700,    2700,    3200,     3500]

        samples = ['D11',  'D12',  'D13',  'D31',  'D32',  'D33']
        x_list  = [-9500, -14800, -23000, -29100, -34700, -42500]
        y_list =  [ 1000,    350,    850,    850,    550,    550]
        z_list =  [ 1700,   1700,   1700,   1700,   1700,   1700]


        for name, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(piezo.y, y)
            yield from bps.mv(piezo.z, z)

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.sleep(1)
                name_fmt = '{sample}_{energy}eV_xbpm{xbpm}_wa{wa}'

                sample_name = name_fmt.format(sample=name, energy=e, xbpm = '%3.1f'%xbpm3.sumY.value, wa='%2.1f'%wa)
                sample_id(user_name='SR', sample_name=sample_name)
                print(f'\n\t=== Sample: {sample_name} ===\n')

                yield from bp.rel_scan(dets, piezo.y, *ypos)
      
            yield from bps.mv(energy, 4050)
            yield from bps.sleep(1)
            yield from bps.mv(energy, 4030)
            

    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)




def NEXAFS_Ca_edge_multi_sintu(t=0.5, name='test'):
    yield from bps.mv(waxs, 52)
    
    dets = [pil300KW]

    # energies = np.arange(4030, 4040, 2).tolist() + np.arange(4040, 4100, 1).tolist() + np.arange(4100, 4126, 2).tolist() + np.arange(4125, 4150, 5).tolist()
    energies = np.linspace(4030, 4150, 121)

    det_exposure_time(t,t) 
    name_fmt = 'nexafs_{sample}_{energy}eV_xbpm{xbpm}'
    for e in energies:                              
        yield from bps.mv(energy, e)
        yield from bps.sleep(1)

        sample_name = name_fmt.format(sample=name, energy=e, xbpm = '%3.1f'%xbpm3.sumY.value)
        RE.md['filename'] = sample_name
        sample_id(user_name='OS', sample_name=sample_name)
        print(f'\n\t=== Sample: {sample_name} ===\n')
        yield from bp.count(dets, num=1)

    yield from bps.mv(energy, 4180)
    yield from bps.sleep(1)
    yield from bps.mv(energy, 4150)
    yield from bps.sleep(1)
    yield from bps.mv(energy, 4120)
    yield from bps.sleep(1)
    yield from bps.mv(energy, 4090)        
    yield from bps.sleep(1)
    yield from bps.mv(energy, 4060)
    yield from bps.sleep(1)
    yield from bps.mv(energy, 4030)

    sample_id(user_name='test', sample_name='test')




# def NEXAFS_db_Ca_edge_multi_sintu(t=0.5, name='test'):

#     yield from bps.mv(waxs, 52)
    
#     dets = [pil1M]

#     energies = np.linspace(4030, 4150, 121)

#     det_exposure_time(t,t) 
#     name_fmt = 'transmission_nexafs_{sample}_{energy}eV_xbpm{xbpm}'
#     for e in energies:                              
#         yield from bps.mv(energy, e)
#         sample_name = name_fmt.format(sample=name, energy=e, xbpm = '%3.1f'%xbpm3.sumY.value)
#         sample_id(user_name='OS', sample_name=sample_name)
#         print(f'\n\t=== Sample: {sample_name} ===\n')
#         yield from bp.count(dets, num=1)


#     sample_id(user_name='test', sample_name='test')









def ex_situ_hardxray_sintu(t=1):
    
    yield from bps.mv(stage.y, 0.1)
    yield from bps.mv(stage.th, 2.5)
    # samples = ['D11', 'D12', 'D13', 'D31', 'D32', 'D33', 'D41', 'D42', 'D43', 'DX1', 'DX2', 'DX3', 'DQ1',  'DQ2',  'DQ3',  'DJ1',  'DJ2',  'DJ3']
    # x_list  = [44700, 39700, 34500, 28800, 23500, 18500, 12400, 7200, 2400, -2800, -8100, -13600, -18700, -24000, -28700, -33900, -39300, -43600]
    # y_list =  [-1600, -1400, -1200, -1200, -1200, -1200, -1000, -999, -999, -2300, -2100,  -1700,  -1100,   -900,   -700,   -500,   -700,   -700]
    # z_list =  [ 2700,  2700,  2700,  2700,  2700,  2700,  2700, 2700, 2700,  2700,  2700,   2700,   2700,   2700,   2700,   2700,   2700,   2700]

    samples = ['JDM_S_1', 'JDM_S_2', 'JDM_S_3', 'JDM_S_4', 'JDM_S_5', 'JDM_S_6', 'JDM_S_7', 'JDM_S_8', 'JDM_S_9', 'JDM_S_10', 'JDM_S_11',
    'JDM_S_12', 'JDM_S_13',  'JDM_S_14', 'JDM_S_15', 'JDM_S_16', 'JDM_S_17', 'JDM_S_18']
    x_list  = [44800, 41800, 39100, 35000, 32500, 29800, 23900, 21700, 18900, 14700, 11700,  9100,  4500,  2300,  -300, -4400, -6900, -9000]
    y_list =  [-1600, -1600, -1200, -1200, -1200, -1200, -1000, -1000, -1000, -1000, -1000, -1000, -1000, -1000, -1000, -1000, -1000, -1000]
    z_list =  [ 2700,  2700,  2700,  2700,  2700,  2700,  2700,  2700,  2700,  2700,  2700,  2700,  2700,  2700,  2700,  2700,  2700,  2700]


    # Detectors, motors:
    dets = [pil1M, pil300KW]
    waxs_range = np.linspace(19.5, 0, 4)
    
    ypos = [0, 400, 3]    
    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'

    det_exposure_time(t,t)

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(piezo.y, y)
            yield from bps.mv(piezo.z, z)

            if wa != 19.5:
                yield from bps.mv(pil1m_pos.y, -60.0)
                name_fmt = '{sam}_wa{waxs}_sdd5m_16.1keV_up'
            elif wa == 19.5:
                yield from bps.mv(pil1m_pos.y, -55.7)
                name_fmt = '{sam}_wa{waxs}_sdd5m_16.1keV_do'

            sample_name = name_fmt.format(sam=sam, waxs='%2.1f'%wa)
            sample_id(user_name='SR', sample_name=sample_name) 
            yield from bp.rel_scan(dets, piezo.y, *ypos)

    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)

    yield from bps.mv(stage.th, 2.5)
    yield from bps.mv(stage.y, -12.9)
    # samples = [ 'W1', 'W2', 'W3', 'D3_1', 'D3_2', 'D3_3', 'X1',  'X2',  'X3',  'Q1',  'Q2',   'Q3',   'J1',   'J2',   'J3', 'Blank']
    # x_list  = [44000, 38700, 33500, 27700, 22300, 16800, 11500,  6000,   800, -4400, -9999, -15700, -21100, -26700, -32100, -38100]
    # y_list =  [-8800, -9700, -8700, -9000, -8800, -9000, -8700, -8700, -8900, -8200, -8500,  -8800,  -8600,  -8600,  -9200,  -8800]
    # z_list =  [ 3300,  3300,  3300,  3300,  3300,  3300,  3300,  3300,  3300,  3300,  3300,   3300,   3300,   3300,   3300,   3300]

    samples = ['JDM_E_1', 'JDM_E_2', 'JDM_E_3', 'JDM_E_4', 'JDM_E_5', 'JDM_E_6', 'JDM_E_7', 'JDM_E_8', 'JDM_E_9', 'JDM_E_10', 'JDM_E_11',
    'JDM_E_12', 'JDM_E_13',  'JDM_E_14',  'JDM_E_15']
    x_list  = [42000, 38000, 33000, 26000, 20500, 14500,  6500,   800, -5500, -11000, -17000, -21400, -26500, -32500, -39400]
    y_list =  [-9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000, -9000,  -9000,  -9000,  -9000,  -9000,  -9000,  -9000]
    z_list =  [ 4500,  4500,  4500,  4500,  4500,  4500,  4500,  4500,  4500,   4500,   4500,   4500,   4500,   4500,   4500]

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(piezo.y, y)
            yield from bps.mv(piezo.z, z)

            if wa != 19.5:
                yield from bps.mv(pil1m_pos.y, -60.0)
                name_fmt = '{sam}_wa{waxs}_sdd5m_16.1keV_up'
            elif wa == 19.5:
                yield from bps.mv(pil1m_pos.y, -55.7)
                name_fmt = '{sam}_wa{waxs}_sdd5m_16.1keV_do'

            sample_name = name_fmt.format(sam=sam, waxs='%2.1f'%wa)
            sample_id(user_name='SR', sample_name=sample_name) 
            yield from bp.rel_scan(dets, piezo.y, *ypos)
    
            
    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)








def ex_situ_hardxray_sintu_2021_2(t=1):
    # Detectors, motors:
    dets = [pil1M, pil300KW]
    waxs_range = np.linspace(19.5, 0, 4)
    ypos = [0, 400, 3]    

    yield from bps.mv(stage.y, 0)
    yield from bps.mv(stage.th, 2.5)

    # samples = ['O1-20', 'O1-05', 'O1-00', 'O2-45', 'O2-35', 'O2-20', 'O2-05', 'O2-00']
    # x_list  = [39000, 27000,  15400, 3600, -7800, -19800, -31000, -43200]
    # y_list =  [ 5800,  6000,  6000,  6000,  5600,   6000,   6000,   6000]
    # z_list =  [    0,     0,     0,     0,     0,      0,      0,      0]
    

    samples = ['O1-20-r', 'O1-05-r', 'O1-00-r']
    x_list  = [38400, 27000,  15200]
    y_list =  [ 5400,  5400,  6400]
    z_list =  [    0,     0,     0]
    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'

    det_exposure_time(t,t)

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(piezo.y, y)
            yield from bps.mv(piezo.z, z)

            if wa != 19.5:
                yield from bps.mv(pil1m_pos.y, -60.0)
                name_fmt = '{sam}_wa{waxs}_sdd5m_16.1keV_up'
            elif wa == 19.5:
                yield from bps.mv(pil1m_pos.y, -55.7)
                name_fmt = '{sam}_wa{waxs}_sdd5m_16.1keV_do'

            sample_name = name_fmt.format(sam=sam, waxs='%2.1f'%wa)
            sample_id(user_name='SR', sample_name=sample_name) 
            yield from bp.rel_scan(dets, piezo.y, *ypos)

    # sample_id(user_name='test', sample_name='test')
    # det_exposure_time(0.3,0.3)

    # yield from bps.mv(stage.th, 2.5)
    # yield from bps.mv(stage.y, -8)

    # ypos = [0, 800, 3]   

    # samples = ['TG3', 'TG2', 'TG1', 'T-4', 'T-3', 'T-2', 'T-1', 'P-6', 'P-5', 'P-4', 'P-3', 'P-2', 'P-1']
    # x_list  = [45200, 37000, 27800, 19600,  11600,   3000, -3200, -12200, -19000,  -23000, -28200, -35200, -42400]
    # y_list =  [-7200, -7200, -7200, -7200,  -7200,  -7200, -7200, -7200, -7200, -7400,  -7400,  -7400,  -7400]
    # z_list =  [    0,     0,     0,     0,      0,      0,      0]
    # assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    # assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'

    # for wa in waxs_range:
    #     yield from bps.mv(waxs, wa)
    #     for sam, x, y, z in zip(samples, x_list, y_list, z_list):
    #         yield from bps.mv(piezo.x, x)
    #         yield from bps.mv(piezo.y, y)
    #         yield from bps.mv(piezo.z, z)

    #         if wa != 19.5:
    #             yield from bps.mv(pil1m_pos.y, -60.0)
    #             name_fmt = '{sam}_wa{waxs}_sdd5m_16.1keV_up'
    #         elif wa == 19.5:
    #             yield from bps.mv(pil1m_pos.y, -55.7)
    #             name_fmt = '{sam}_wa{waxs}_sdd5m_16.1keV_do'

    #         sample_name = name_fmt.format(sam=sam, waxs='%2.1f'%wa)
    #         sample_id(user_name='SR', sample_name=sample_name) 
    #         yield from bp.rel_scan(dets, piezo.y, *ypos)
    
            
    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)





def ex_situ_hardxray_humidity_2021_2(t=1):
    # Detectors, motors:
    dets = [pil1M, pil300KW]
    waxs_range = np.linspace(19.5, 0, 4)
    ypos = [0, 0.2, 3]    

    # samples = ['kapton_pos1', 'Hyd_On_Ca_1_pos2', 'Hyd_On_Ca_2_pos3', 'Hyd_ARA_Bu_1_pos4', 'Hyd_ARA_Bu_2_pos5', 'Hyd_On_Bu_1_pos6', 'Hyd_On_Bu_2_pos7', 'Hyd_On_Bu_3_pos8']
    # samples = ['kapton_pos1', 'kapton_pos2', 'kapton_pos3', 'kapton_pos4', 'kapton_pos5', 'kapton_pos6', 'kapton_pos7', 'kapton_pos8']
    samples = ['Hyd_ARA_PL_1_pos1', 'Hyd_ARA_PL_2_pos2', 'Hyd_ARA_PL_3_pos3', 'Hyd_ARA_Bu_3_pos4', 'Hyd_ARA_Ca_1_pos5', 'Hyd_ARA_Ca_2_pos6', 'Hyd_ARA_Ca_3_pos7', 'Hyd_On_Ca_3_pos8']
    x_list  = [30.3, 23.8, 17.4, 11.1, 4.9, -1.5, -7.8, -14.3]
    y_list =  [-1,   -1,   -1,   -1,  -1,   -1,   -1,    -1]
    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'

    det_exposure_time(t,t)

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y in zip(samples, x_list, y_list):
            yield from bps.mv(stage.x, x)
            yield from bps.mv(stage.y, y)

            if wa != 19.5:
                yield from bps.mv(pil1m_pos.y, -60.0)
                name_fmt = '{sam}_wa{waxs}_sdd5m_16.1keV_up_3s_bpm{bpm}'
            elif wa == 19.5:
                yield from bps.mv(pil1m_pos.y, -55.7)
                name_fmt = '{sam}_wa{waxs}_sdd5m_16.1keV_do_3s_bpm{bpm}'

            bpm1 = xbpm3.sumX.value
            sample_name = name_fmt.format(sam=sam, waxs='%2.1f'%wa, bpm = '%1.3f'%bpm1)
            sample_id(user_name='SR', sample_name=sample_name)
            yield from bp.rel_scan(dets, stage.y, *ypos)

    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)


def ex_situ_caedge_humidity_2021_2(t=1):

    # Detectors, motors:
    dets = [pil1M, pil300KW]
    waxs_range = np.linspace(19.5, 0, 4)
    # waxs_range = np.linspace(45.5, 0, 8)
    ypos = [0, 0.2, 3]

    energies = [4030, 4040, 4050, 4055, 4065, 4075, 4105]


    # samples = ['kapton_pos1', 'Hyd_On_Ca_1_pos2', 'Hyd_On_Ca_2_pos3', 'Hyd_ARA_Bu_1_pos4', 'Hyd_ARA_Bu_2_pos5', 'Hyd_On_Bu_1_pos6', 'Hyd_On_Bu_2_pos7', 'Hyd_On_Bu_3_pos8']
    # samples = ['kapton_pos1', 'kapton_pos2', 'kapton_pos3', 'kapton_pos4', 'kapton_pos5', 'kapton_pos6', 'kapton_pos7', 'kapton_pos8']
    # samples = ['Hyd_ARA_PL_1_pos1', 'Hyd_ARA_PL_2_pos2', 'Hyd_ARA_PL_3_pos3', 'Hyd_ARA_Bu_3_pos4', 'Hyd_ARA_Ca_1_pos5', 'Hyd_ARA_Ca_2_pos6', 'Hyd_ARA_Ca_3_pos7', 'Hyd_On_Ca_3_pos8']
    # samples = ['Hyd_ARA_Bu_1_pos1', 'Hyd_ARA_Bu_2_pos2', 'Hyd_ARA_Bu_3_pos3', 'Hyd_ARA_Ca_1_pos4', 'Hyd_ARA_Ca_2_pos5', 'Hyd_ARA_Ca_3_pos6', 'Hyd_ARA_PL_1_pos7', 'Hyd_On_PL_2_pos8']
    # samples = ['Hyd_ARA_Bu_1_more_angles_pos1', 'Hyd_ARA_Ca_1_more_angles_pos4']
    # samples = ['kapton_more_angles_pos1', 'kapton_more_angles_pos4']
    samples = ['Hyd_On_Bu_1_pos1', 'Hyd_On_Bu_2_pos2', 'Hyd_On_Bu_3_pos3', 'Hyd_On_Bu_4_pos4', 'Hyd_On_Ca_1_pos5', 'Hyd_On_Ca_2_pos6', 'Hyd_On_Ca_3_pos7', 'Hyd_On_Ca_4_pos8']

    x_list  = [29.75, 23.3, 17.0, 10.7,  4.4, -2.0, -8.2, -14.5]
    y_list =  [ -1.2, -1.2, -1.2, -1.2, -1.2, -1.2, -1.2,  -1.2]
    # x_list  = [29.75, 10.7]
    # y_list =  [ -1.2, -1.2]
    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'

    det_exposure_time(t,t)

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y in zip(samples, x_list, y_list):
            yield from bps.mv(stage.x, x)
            yield from bps.mv(stage.y, y)

            if wa != 19.5:
                yield from bps.mv(pil1m_pos.y, -60.0)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_16.1keV_up_3s_bpm{bpm}'
            
            elif wa == 19.5:
                yield from bps.mv(pil1m_pos.y, -55.7)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_16.1keV_do_3s_bpm{bpm}'

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.sleep(1)

                bpm1 = xbpm3.sumX.value
                sample_name = name_fmt.format(sam=sam, energy=e, waxs='%2.1f'%wa, bpm = '%1.3f'%bpm1)
                sample_id(user_name='SR', sample_name=sample_name)
                yield from bp.rel_scan(dets, stage.y, *ypos)
                
            yield from bps.mv(energy, 4080)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 4050)
            yield from bps.sleep(2)

    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)




def ex_situ_nexafscaedge_humidity_2021_2(t=1):
    yield from bps.mv(GV7.close_cmd, 1)
    yield from bps.sleep(2)
    yield from bps.mv(GV7.close_cmd, 1)

    # Detectors, motors:
    dets = [pil300KW]
    waxs_range = [50]

    energies = np.linspace(4030, 4150, 121)

    # samples = ['Hyd_ARA_Bu_1_pos1', 'Hyd_ARA_Bu_2_pos2', 'Hyd_ARA_Bu_3_pos3', 'Hyd_ARA_Ca_1_pos4', 'Hyd_ARA_Ca_2_pos5', 'Hyd_ARA_Ca_3_pos6', 'Hyd_ARA_PL_1_pos7', 'Hyd_On_PL_2_pos8']
    # samples = ['kapton_pos1', 'kapton_pos4']
    samples = ['Hyd_On_Bu_1_pos1', 'Hyd_On_Bu_2_pos2', 'Hyd_On_Ca_1_pos5', 'Hyd_On_Ca_2_pos6']
    
    # x_list  = [29.75, 23.3, 17.0, 10.7,  4.4, -2.0, -8.2, -14.5]
    # y_list =  [ -1.4, -1.4, -1.4, -1.4, -1.4, -1.4, -1.4,  -1.4]
    # x_list  = [29.75, 10.7]
    # y_list =  [ -1.2, -1.2]

    x_list  = [29.75, 23.3, 4.4, -2.0]
    y_list =  [ -1.4, -1.4, -1.4, -1.4]

    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'

    det_exposure_time(t,t)

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y in zip(samples, x_list, y_list):
            yield from bps.mv(stage.x, x)
            yield from bps.mv(stage.y, y)

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.sleep(1)
                
                name_fmt = 'nexafs_{sam}_{energy}eV_wa{waxs}_16.1keV_3s_bpm{bpm}'

                bpm1 = xbpm3.sumX.value
                sample_name = name_fmt.format(sam=sam, energy=e, waxs='%2.1f'%wa, bpm = '%1.3f'%bpm1)
                sample_id(user_name='SR', sample_name=sample_name)
                yield from bp.count(dets, num=1)

            yield from bps.mv(energy, 4120)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 4090)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 4060)
            yield from bps.sleep(2)

    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)

    yield from bps.mv(GV7.open_cmd, 1)
    yield from bps.sleep(2)
    yield from bps.mv(GV7.open_cmd, 1)





def ex_situ_caedge_2021_2(t=1):

    # Detectors, motors:
    dets = [pil1M, pil300KW]
    waxs_range = np.linspace(39, 0, 7)
    ypos = [0, 100]

    energies = [4030, 4040, 4050, 4055, 4075, 4105]

    yield from bps.mv(stage.y, 0)
    yield from bps.mv(stage.th, 2.5)


    samples = ['R1_1', 'R1_2', 'R1_3', 'R2_1', 'R2_2', 'R2_3', 'R3_1', 'R3_2', 'R3_3', 'R3_4', 'R4_1', 'R4_2', 'R4_3', 'R4_4',
    'R5_1', 'R5_2', 'R5_3', 'R5_4', 'R6_1', 'R6_2', 'R6_3', 'R6_4', 'R7_1', 'R7_2', 'R7_3', 'R7_4']
    
    # samples = ['GoSAMT_Bu_1', 'GoSAMT_Bu_2', 'GoSAMT_Bu_3', 'GoSAMT_Bu_4', 'GoSAMT_Ca_1', 'GoSAMT_Ca_2', 'GoSAMT_Ca_3', 'GoSAMT_PL_1', 'GoSAMT_PL_2', 'GoSAMT_PL_3', 'Dry_ARA_Bu_1', 'Dry_ARA_Bu_2', 'Dry_ARA_Ca_1', 'Dry_ARA_Ca_2',
    # 'Dry_On_Bu_1', 'Dry_On_Bu_2', 'Dry_Ca_Bu_1', 'Dry_On_Ca_2']


    x_list  = [46400, 43700, 40900, 34500, 31350, 28700, 21400, 18600, 16100, 12800, 7950, 5100, 1800, -1500, -6750, -10300, -13600, -16800,
    -22200, -25200, -28100, -30800, -35800, -39000, -41500, -43900]
    y_list =  [ 6000,  6000,  6000,  6000,  6000,  6000,  6000,  6000,  6000,  6000, 6000, 6000, 6000,  6000,  6000,   6000,   6000,   6000,
      6000,   6000,   6000,   6000,   6000,   6000,   6000,   6000]
    z_list =  [ 4700,  4700,  4700,  4700,  4700,  4700,  4700,  4600,  4600,  4600, 4500, 4500, 4500,  4500,  4000,   4000,   4000,   4000,
      3700,   3700,   3700,   3700,   3500,   3500,   3500,   3500]


    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'
    assert len(x_list) == len(z_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(z_list)})'

    det_exposure_time(t,t)

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(piezo.y, y)
            yield from bps.mv(piezo.z, z)

            if wa != 19.5:
                yield from bps.mv(pil1m_pos.y, -60.0)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_up_3s_bpm{bpm}'
            
            elif wa == 19.5:
                yield from bps.mv(pil1m_pos.y, -55.7)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_do_3s_bpm{bpm}'

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.sleep(1)

                bpm1 = xbpm3.sumX.value
                sample_name = name_fmt.format(sam=sam, energy=e, waxs='%2.1f'%wa, bpm = '%1.3f'%bpm1)
                sample_id(user_name='SR', sample_name=sample_name)
                yield from bp.rel_list_scan(dets, piezo.y, ypos)
                
            yield from bps.mv(energy, 4080)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 4050)
            yield from bps.sleep(2)

    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)


    yield from bps.mv(stage.y, -7.8)
    yield from bps.mv(stage.th, 2.5)


    samples = ['P1_1', 'P1_2', 'P1_3', 'P1_4', 'P1_5', 'P2_1', 'P2_2', 'P2_3', 'P2_4', 'P3_1', 'P3_2', 'P3_3', 'P3_4', 'P4_1', 'P4_2', 'P4_3', 'P4_4',
    'P5_1', 'P5_2', 'P5_3']

    x_list  = [44900, 40900, 36700, 32500, 28500, 21100, 17400, 13900, 10850,  3600,  -200, -3950, -8600, -15300, -18800, -23000, -27000, -33600,
    -37650, -42100]
    y_list =  [-6000, -6000,- 6000, -6000, -6400, -6000, -6000, -6000, -6000, -6000, -6000, -6000, -6000,  -6000,  -6000,  -6000,  -6000,  -6000,
     -6000,  -6000]
    z_list =  [ 4700,  4700,  4700,  4600,  4600,  4500,  4500,  4400,  4400,  4200,  4200,  4200,  4100,   4100,   4000,   4000,   4000,   4000,
      3700,   3700]

    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'
    assert len(x_list) == len(z_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(z_list)})'

    det_exposure_time(t,t)

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(piezo.y, y)
            yield from bps.mv(piezo.z, z)

            if wa != 19.5:
                yield from bps.mv(pil1m_pos.y, -60.0)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_up_3s_bpm{bpm}'
            
            elif wa == 19.5:
                yield from bps.mv(pil1m_pos.y, -55.7)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_do_3s_bpm{bpm}'

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.sleep(1)

                bpm1 = xbpm3.sumX.value
                sample_name = name_fmt.format(sam=sam, energy=e, waxs='%2.1f'%wa, bpm = '%1.3f'%bpm1)
                sample_id(user_name='SR', sample_name=sample_name)
                yield from bp.rel_list_scan(dets, piezo.y, ypos)
                
            yield from bps.mv(energy, 4080)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 4050)
            yield from bps.sleep(2)




def ex_situ_nexafscaedge_2021_2(t=1):
    yield from bps.mv(GV7.close_cmd, 1)
    yield from bps.sleep(2)
    yield from bps.mv(GV7.close_cmd, 1)

    # Detectors, motors:
    dets = [pil300KW]
    waxs_range = [50]

    energies = np.linspace(4030, 4150, 121)

    # samples = ['R1_1', 'R2_1', 'R3_1', 'R4_1', 'R5_1', 'R6_1', 'R7_1']
    # x_list  = [46400,  34500, 21400,  7950, -6750, -22200, -35800]
    # y_list =  [ 6000,   6000,  6000,  6000, 6000,    6000,   6000]
    # z_list =  [ 4700,   4700,   4700, 4500,  4000,   3700,   3500]

    # samples = ['P1_1', 'P2_1', 'P3_1', 'P4_1', 'P5_1']
    # x_list  = [44900, 21100,  3600, -15300, -33600]
    # y_list =  [-6000, -6000,- 6000,  -6000,  -6000]
    # z_list =  [ 4700,  4500,  4200,   3900,   3700]



    samples = ['GoSAMT_Bu_1', 'GoSAMT_Ca_1', 'GoSAMT_PL_1', ]

    x_list  = [46400, 29500, 7200]
    y_list =  [ 6000,  6000, 6000]
    z_list =  [ 4700,  4500, 4300]

    yield from bps.mv(stage.x, 0)
    yield from bps.mv(stage.y, 0.4)
    yield from bps.mv(stage.th, 2.5)


    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'

    det_exposure_time(t,t)

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(piezo.z, z)

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.sleep(0.5)
                
                name_fmt = 'nexafs_{sam}_{energy}eV_wa{waxs}_bpm{bpm}'

                bpm1 = xbpm3.sumX.value
                sample_name = name_fmt.format(sam=sam, energy=e, waxs='%2.1f'%wa, bpm = '%1.3f'%bpm1)
                sample_id(user_name='SR', sample_name=sample_name)
                yield from bp.count(dets, num=1)

            yield from bps.mv(energy, 4110)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 4080)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 4050)
            yield from bps.sleep(2)

    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)

    yield from bps.mv(GV7.open_cmd, 1)
    yield from bps.sleep(2)
    yield from bps.mv(GV7.open_cmd, 1)




def ex_situ_caedge_nosmaract_2021_2(t=1):

    # Detectors, motors:
    dets = [pil1M, pil300KW]
    waxs_range = np.linspace(39, 0, 7)
    ypos = [0, 0.2]

    energies = [4030, 4040, 4050, 4055, 4075, 4105]

    yield from bps.mv(stage.y, 0)
    yield from bps.mv(stage.th, 2.5)


    # samples = ['R1_1', 'R1_2', 'R1_3', 'R2_1', 'R2_2', 'R2_3', 'R3_1', 'R3_2', 'R3_3', 'R3_4', 'R4_1', 'R4_2', 'R4_3', 'R4_4',
    # 'R5_1', 'R5_2', 'R5_3', 'R5_4', 'R6_1', 'R6_2', 'R6_3', 'R6_4', 'R7_1', 'R7_2', 'R7_3', 'R7_4']
    
    samples = ['GoSAMT_Bu_1', 'GoSAMT_Bu_2', 'GoSAMT_Bu_3', 'GoSAMT_Bu_4', 'GoSAMT_Ca_1', 'GoSAMT_Ca_2', 'GoSAMT_Ca_3', 'GoSAMT_PL_1', 'GoSAMT_PL_2', 
    'GoSAMT_PL_3', 'Dry_ARA_Bu_1', 'Dry_ARA_Bu_2', 'Dry_ARA_Ca_1', 'Dry_ARA_Ca_2', 'Dry_On_Bu_1', 'Dry_On_Bu_2', 'Dry_Ca_Bu_1', 'Dry_On_Ca_2']


    # x_list  = [46400, 43700, 40900, 34500, 31350, 28700, 21400, 18600, 16100, 12800, 7950, 5100, 1800, -1500, -6750, -10300, -13600, -16800,
    # -22200, -25200, -28100, -30800, -35800, -39000, -41500, -43900]
    # y_list =  [ 6000,  6000,  6000,  6000,  6000,  6000,  6000,  6000,  6000,  6000, 6000, 6000, 6000,  6000,  6000,   6000,   6000,   6000,
    #   6000,   6000,   6000,   6000,   6000,   6000,   6000,   6000]
    # z_list =  [ 4700,  4700,  4700,  4700,  4700,  4700,  4700,  4600,  4600,  4600, 4500, 4500, 4500,  4500,  4000,   4000,   4000,   4000,
    #   3700,   3700,   3700,   3700,   3500,   3500,   3500,   3500]

    x_list  = [46400, 43700, 39700, 36700, 29500, 25300, 21000, 7200, 3400,  100, -12100, -16300, -19300, -22600, -25600, -31300,-37300, -43300]
    y_list =  [ 6000,  6000,  6000,  6000,  6000,  6000,  6000, 6000, 6000, 6000,   6000,   6000,   6000,   6000,   6000,   6000,  6000,   6000]
    z_list =  [ 4700,  4700,  4700,  4700,  4500,  4500,  4500, 4300, 4300, 4300,   3900,   3900,   3900,   3900,   3900,   3500,  3500,   3500]


    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'
    assert len(x_list) == len(z_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(z_list)})'

    det_exposure_time(t,t)

    yield from bps.mv(piezo.y, 6000)

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(stage.y, 0)
            yield from bps.mv(piezo.z, z)

            if wa != 19.5:
                yield from bps.mv(pil1m_pos.y, -60.0)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_up_3s_bpm{bpm}'
            
            elif wa == 19.5:
                yield from bps.mv(pil1m_pos.y, -55.7)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_do_3s_bpm{bpm}'

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.sleep(1)

                bpm1 = xbpm3.sumX.value
                sample_name = name_fmt.format(sam=sam, energy=e, waxs='%2.1f'%wa, bpm = '%1.3f'%bpm1)
                sample_id(user_name='SR', sample_name=sample_name)
                yield from bp.rel_list_scan(dets, stage.y, ypos)
                
            yield from bps.mv(energy, 4080)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 4050)
            yield from bps.sleep(2)

    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)


    yield from bps.mv(stage.y, -7.4)
    yield from bps.mv(stage.x, -0.8)
    yield from bps.mv(stage.th, 2.5)


    samples = ['P1_1', 'P1_2', 'P1_3', 'P1_4', 'P1_5', 'P2_1', 'P2_2', 'P2_3', 'P2_4', 'P3_1', 'P3_2', 'P3_3', 'P3_4', 'P4_1', 'P4_2', 'P4_3', 'P4_4',
    'P5_1', 'P5_2', 'P5_3']

    x_list  = [44900, 40900, 36700, 32500, 28500, 21100, 17400, 13900, 10850,  3600,  -200, -3950, -8600, -15300, -18800, -23000, -27000, -33600,
    -37650, -42100]
    y_list =  [-6000, -6000,- 6000, -6000, -6400, -6000, -6000, -6000, -6000, -6000, -6000, -6000, -6000,  -6000,  -6000,  -6000,  -6000,  -6000,
     -6000,  -6000]
    z_list =  [ 4700,  4700,  4700,  4600,  4600,  4500,  4500,  4400,  4400,  4200,  4200,  4200,  4100,   4100,   4000,   4000,   4000,   4000,
      3700,   3700]

    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'
    assert len(x_list) == len(z_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(z_list)})'

    det_exposure_time(t,t)


    yield from bps.mv(piezo.y, -6000)

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(stage.y, -7.4)
            yield from bps.mv(piezo.z, z)

            if wa != 19.5:
                yield from bps.mv(pil1m_pos.y, -60.0)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_up_3s_bpm{bpm}'
            
            elif wa == 19.5:
                yield from bps.mv(pil1m_pos.y, -55.7)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_do_3s_bpm{bpm}'

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.sleep(1)

                bpm1 = xbpm3.sumX.value
                sample_name = name_fmt.format(sam=sam, energy=e, waxs='%2.1f'%wa, bpm = '%1.3f'%bpm1)
                sample_id(user_name='SR', sample_name=sample_name)
                yield from bp.rel_list_scan(dets, stage.y, ypos)
                
            yield from bps.mv(energy, 4080)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 4050)
            yield from bps.sleep(2)
    yield from bps.mv(stage.x, 0)






def ex_situ_znedge_nosmaract_2021_2(t=1):

    # Detectors, motors:
    dets = [pil1M, pil300KW]
    waxs_range = np.linspace(19.5, 0, 4)
    ypos = [0, 0.2, 0.4, 0.6]
    # ypos = [0, 0.2]

    energies = [9640, 9660, 9665, 9670, 9680, 9700]


    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)

    yield from bps.mv(stage.th, 2.5)


    samples = ['R1_1', 'R1_2', 'R1_3', 'R2_1', 'R2_2', 'R2_3', 'R3_1', 'R3_2', 'R3_3', 'R3_4', 'R4_1', 'R4_2', 'R4_3', 'R4_4', 'R5_1', 'R5_2', 'R5_3', 'R5_4', 'R6_1', 'R6_2', 'R6_3', 'R6_4', 'R7_1', 'R7_2', 'R7_3', 'R7_4']

    x_list  = [47100,   44300,  41700,  35200,  32000,  29400,  22200,  19300,  16800,  13600,   8700,   5800,   2500,   -700,  -6050,  -9600, -12900, -16100, -21500, -24500, -27300, -30100, -35100, -38300, -40800, -43200]
    y_list =  [6000,   6000,  6000,  6000,  6000,  6000,   6000,   6000,  6000,  6000, 6000, 6000, 6000, 6000,  6000,  6000,   6000,   6000,   6000,   6000,   6000,   6000,   6000,   6000,   6000,   6000]
    z_list =  [ 4000,  4000,  4000,  4000,  4000,  4000,   4000,   4000,  4000,  4000, 4000, 4000, 4000, 4000,  4000,  4000,   4000,   4000,   4000,   4000,   4000,   4000,   4000,   4000,   4000,   4000]

    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'
    assert len(x_list) == len(z_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(z_list)})'


    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y, z in zip(samples, x_list, y_list, z_list):
            yield from bps.mv(piezo.x, x)
            yield from bps.mv(stage.y, 0.2) #0.2
            yield from bps.mv(piezo.z, z)

            if wa != 19.5:
                yield from bps.mv(pil1m_pos.y, -60.0)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_up_bpm{bpm}'
            
            elif wa == 19.5:
                yield from bps.mv(pil1m_pos.y, -55.7)
                name_fmt = '{sam}_{energy}eV_wa{waxs}_sdd5m_do_bpm{bpm}'

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.sleep(1)

                bpm1 = xbpm3.sumX.value
                sample_name = name_fmt.format(sam=sam, energy=e, waxs='%2.1f'%wa, bpm = '%1.3f'%bpm1)
                sample_id(user_name='SR', sample_name=sample_name)
                yield from bp.rel_list_scan(dets, stage.y, ypos)
                
            yield from bps.mv(energy, 9670)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 9640)
            yield from bps.sleep(2)



def ex_situ_nexafsznedge_2021_2(t=1):
    yield from bps.mv(GV7.close_cmd, 1)
    yield from bps.sleep(2)
    yield from bps.mv(GV7.close_cmd, 1)


    # Detectors, motors:
    dets = [pil300KW]
    waxs_range = [65]

    energies = np.linspace(9640, 9740, 101)

    samples = ['kapton', 'R1_1', 'R2_1', 'R3_1', 'R4_1', 'R5_1', 'R6_1', 'R7_1']

    x_list  = [25000, 47100, 35200, 22200,  8700, -6050, -21500, -35100]
    y_list =  [6000,  6000,   6000,  6000,  6000,   6000,   6000,  6000]
    z_list =  [4000,  4000,   4000,  4000,  4000,   4000,   4000,  4000]

    assert len(x_list) == len(samples), f'Number of X coordinates ({len(x_list)}) is different from number of samples ({len(samples)})'
    assert len(x_list) == len(y_list), f'Number of X coordinates ({len(x_list)}) is different from number of Y coord ({len(y_list)})'

    det_exposure_time(t,t)

    for wa in waxs_range:
        yield from bps.mv(waxs, wa)
        for sam, x, y in zip(samples, x_list, y_list):
            yield from bps.mv(piezo.x, x)

            for k, e in enumerate(energies):                              
                yield from bps.mv(energy, e)
                yield from bps.sleep(1)
                
                name_fmt = 'nexafs_{sam}_{energy}eV_wa{waxs}_bpm{bpm}'

                bpm1 = xbpm3.sumX.value
                sample_name = name_fmt.format(sam=sam, energy=e, waxs='%2.1f'%wa, bpm = '%1.3f'%bpm1)
                sample_id(user_name='SR', sample_name=sample_name)
                yield from bp.count(dets, num=1)

            yield from bps.mv(energy, 9710)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 9685)
            yield from bps.sleep(2)
            yield from bps.mv(energy, 9660)
            yield from bps.sleep(2)

    sample_id(user_name='test', sample_name='test')
    det_exposure_time(0.3,0.3)

    yield from bps.mv(GV7.open_cmd, 1)
    yield from bps.sleep(2)
    yield from bps.mv(GV7.open_cmd, 1)
