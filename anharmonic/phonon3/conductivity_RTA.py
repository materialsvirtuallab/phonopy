import numpy as np
from phonopy.phonon.group_velocity import get_group_velocity
from phonopy.units import THzToEv, THz, Angstrom
from phonopy.phonon.thermal_properties import mode_cv as get_mode_cv
from anharmonic.file_IO import write_kappa_to_hdf5, write_triplets, read_gamma_from_hdf5, write_grid_address
from anharmonic.phonon3.conductivity import Conductivity
from anharmonic.phonon3.imag_self_energy import ImagSelfEnergy
from anharmonic.phonon3.triplets import get_grid_points_by_rotations

def get_thermal_conductivity_RTA(
        interaction,
        symmetry,
        temperatures=np.arange(0, 1001, 10, dtype='double'),
        sigmas=[],
        mass_variances=None,
        grid_points=None,
        is_isotope=False,
        mesh_divisors=None,
        coarse_mesh_shifts=None,
        cutoff_mfp=None, # in micrometre
        no_kappa_stars=False,
        gv_delta_q=1e-4, # for group velocity
        write_gamma=False,
        read_gamma=False,
        input_filename=None,
        output_filename=None,
        log_level=0):

    if log_level:
        print "-------------------- Lattice thermal conducitivity (RTA) --------------------"

    br = Conductivity_RTA(interaction,
                          symmetry,
                          grid_points=grid_points,
                          temperatures=temperatures,
                          sigmas=sigmas,
                          is_isotope=is_isotope,
                          mass_variances=mass_variances,
                          mesh_divisors=mesh_divisors,
                          coarse_mesh_shifts=coarse_mesh_shifts,
                          cutoff_mfp=cutoff_mfp,
                          no_kappa_stars=no_kappa_stars,
                          gv_delta_q=gv_delta_q,
                          log_level=log_level)

    if read_gamma:
        if not _set_gamma_from_file(br, filename=input_filename):
            print "Reading collisions failed."
            return False
        
    for i in br:
        if write_gamma:
            _write_gamma(br, interaction, i, filename=output_filename)
        if log_level > 1:
            _write_triplets(interaction)

    if grid_points is None:
        br.set_kappa_at_sigmas()
        _write_kappa(br, filename=output_filename, log_level=log_level)

    return br
        
def _write_gamma(br, interaction, i, filename=None):
    grid_points = br.get_grid_points()
    group_velocities = br.get_group_velocities()
    mode_heat_capacities = br.get_mode_heat_capacities()
    mspp = br.get_mean_square_pp_strength()
    mesh = br.get_mesh_numbers()
    mesh_divisors = br.get_mesh_divisors()
    temperatures = br.get_temperatures()
    gamma = br.get_gamma()
    gamma_isotope = br.get_gamma_isotope()
    sigmas = br.get_sigmas()
    
    gp = grid_points[i]
    frequencies = interaction.get_phonons()[0][gp]
    
    for j, sigma in enumerate(sigmas):
        if gamma_isotope is not None:
            gamma_isotope_at_sigma = gamma_isotope[j, i]
        else:
            gamma_isotope_at_sigma = None
        write_kappa_to_hdf5(temperatures,
                            mesh,
                            frequency=frequencies,
                            group_velocity=group_velocities[i],
                            heat_capacity=mode_heat_capacities[i],
                            kappa=None,
                            gamma=gamma[j, :, i],
                            gamma_isotope=gamma_isotope_at_sigma,
                            mspp=mspp[i],
                            mesh_divisors=mesh_divisors,
                            grid_point=gp,
                            sigma=sigma,
                            filename=filename)

def _write_triplets(interaction, filename=None):
    triplets, weights = interaction.get_triplets_at_q()
    grid_address = interaction.get_grid_address()
    mesh = interaction.get_mesh_numbers()
    write_triplets(triplets,
                   weights,
                   mesh,
                   grid_address,
                   grid_point=triplets[0, 0],
                   filename=filename)
    write_grid_address(grid_address, mesh, filename=filename)

def _write_kappa(br, filename=None, log_level=0):
    temperatures = br.get_temperatures()
    sigmas = br.get_sigmas()
    gamma = br.get_gamma()
    gamma_isotope = br.get_gamma_isotope()
    mesh = br.get_mesh_numbers()
    mesh_divisors = br.get_mesh_divisors()
    frequencies = br.get_frequencies()
    gv = br.get_group_velocities()
    mode_cv = br.get_mode_heat_capacities()
    mspp = br.get_mean_square_pp_strength()
    qpoints = br.get_qpoints()
    weights = br.get_grid_weights()
    # num_sampling_points = br.get_number_of_sampling_points()
    
    kappa = br.get_kappa()
    
    for i, sigma in enumerate(sigmas):
        kappa_at_sigma = kappa[i]
        if gamma_isotope is not None:
            gamma_isotope_at_sigma = gamma_isotope[i]
        else:
            gamma_isotope_at_sigma = None
        if log_level:
            print "----------- Thermal conductivity (W/m-k)",
            if sigma:
                print "for sigma=%s -----------" % sigma
            else:
                print "with tetrahedron method -----------"
            print ("#%6s     " + " %-9s" * 6) % ("T(K)", "xx", "yy", "zz",
                                                "yz", "xz", "xy")
            for t, k in zip(temperatures, kappa_at_sigma):
                print ("%7.1f" + " %9.3f" * 6) % ((t,) + tuple(k))
            print
        write_kappa_to_hdf5(temperatures,
                            mesh,
                            frequency=frequencies,
                            group_velocity=gv,
                            heat_capacity=mode_cv,
                            kappa=kappa_at_sigma,
                            gamma=gamma[i],
                            gamma_isotope=gamma_isotope_at_sigma,
                            mspp=mspp,
                            qpoint=qpoints,
                            weight=weights,
                            mesh_divisors=mesh_divisors,
                            sigma=sigma,
                            filename=filename)
               
def _set_gamma_from_file(br, filename=None):
    sigmas = br.get_sigmas()
    mesh = br.get_mesh_numbers()
    mesh_divisors = br.get_mesh_divisors()
    grid_points = br.get_grid_points()
    temperatures = br.get_temperatures()
    num_band = br.get_frequencies().shape[1]

    gamma = np.zeros((len(sigmas),
                      len(temperatures),
                      len(grid_points),
                      num_band), dtype='double')
    gamma_iso = np.zeros((len(sigmas),
                          len(grid_points),
                          num_band), dtype='double')
    is_isotope = False

    for j, sigma in enumerate(sigmas):
        collisions = read_gamma_from_hdf5(
            mesh,
            mesh_divisors=mesh_divisors,
            sigma=sigma,
            filename=filename)
        if collisions is False:
            for i, gp in enumerate(grid_points):
                collisions_gp = read_gamma_from_hdf5(
                    mesh,
                    mesh_divisors=mesh_divisors,
                    grid_point=gp,
                    sigma=sigma,
                    filename=filename)
                if collisions_gp is False:
                    print "Gamma at grid point %d doesn't exist." % gp
                    return False
                else:
                    gamma_gp, gamma_iso_gp = collisions_gp
                    gamma[j, :, i] = gamma_gp
                    if gamma_iso_gp is not None:
                        is_isotope = True
                        gamma_iso[j, i] = gamma_iso_gp
        else:
            gamma_at_sigma, gamma_iso_at_sigma = collisions
            gamma[j] = gamma_at_sigma
            if gamma_iso_at_sigma is not None:
                is_isotope = True
                gamma_iso[j] = gamma_iso_at_sigma
        
    br.set_gamma(gamma)
    # if is_isotope:
    #     br.set_gamma_isotope(gamma_iso)

    return True

class Conductivity_RTA(Conductivity):
    def __init__(self,
                 interaction,
                 symmetry,
                 grid_points=None,
                 temperatures=np.arange(0, 1001, 10, dtype='double'),
                 sigmas=[],
                 is_isotope=False,
                 mass_variances=None,
                 mesh_divisors=None,
                 coarse_mesh_shifts=None,
                 cutoff_mfp=None, # in micrometre
                 no_kappa_stars=False,
                 gv_delta_q=None, # finite difference for group veolocity
                 log_level=0):

        self._pp = None
        self._temperatures = None
        self._sigmas = None
        self._no_kappa_stars = None
        self._gv_delta_q = None
        self._log_level = None
        self._primitive = None
        self._dm = None
        self._frequency_factor_to_THz = None
        self._cutoff_frequency = None
        self._cutoff_mfp = None

        self._symmetry = None
        self._point_operations = None
        self._rotations_cartesian = None
        
        self._grid_points = None
        self._grid_weights = None
        self._grid_address = None

        self._gamma = None
        self._read_gamma = False
        self._read_gamma_iso = False
        self._frequencies = None
        self._gv = None
        self._gamma_iso = None
        self._mean_square_pp_strength = None
        
        self._mesh = None
        self._mesh_divisors = None
        self._coarse_mesh = None
        self._coarse_mesh_shifts = None
        self._conversion_factor = None

        self._is_isotope = None
        self._isotope = None
        self._mass_variances = None
        self._grid_point_count = None

        Conductivity.__init__(self,
                              interaction,
                              symmetry,
                              grid_points=grid_points,
                              temperatures=temperatures,
                              sigmas=sigmas,
                              is_isotope=is_isotope,
                              mass_variances=mass_variances,
                              mesh_divisors=mesh_divisors,
                              coarse_mesh_shifts=coarse_mesh_shifts,
                              cutoff_mfp=cutoff_mfp,
                              no_kappa_stars=no_kappa_stars,
                              gv_delta_q=gv_delta_q,
                              log_level=log_level)

        self._cv = None

        if self._temperatures is not None:
            self._allocate_values()

    def set_kappa_at_sigmas(self):
        num_band = self._primitive.get_number_of_atoms() * 3
        num_sampling_points = 0
        
        for i, grid_point in enumerate(self._grid_points):
            cv = self._cv[i]
            
            # Outer product of group velocities (v x v) [num_k*, num_freqs, 3, 3]
            gv_by_gv_tensor, order_kstar = self._get_gv_by_gv(i)
            num_sampling_points += order_kstar
    
            # Sum all vxv at k*
            gv_sum2 = np.zeros((6, num_band), dtype='double')
            for j, vxv in enumerate(
                ([0, 0], [1, 1], [2, 2], [1, 2], [0, 2], [0, 1])):
                gv_sum2[j] = gv_by_gv_tensor[:, vxv[0], vxv[1]]

            # Boundary scattering
            if self._cutoff_mfp is not None:
                g_boundary = self._get_boundary_scattering(i)
                
            # Kappa
            for j in range(len(self._sigmas)):
                for k in range(len(self._temperatures)):
                    g_sum = self._get_main_diagonal(i, j, k)
                    for l in range(num_band):
                        if i == 0 and l < 3: # Acoustic mode at Gamma (singular)
                            continue
                        self._kappa[j, k] += (
                            gv_sum2[:, l] * cv[k, l] / (g_sum[l] * 2) *
                            self._conversion_factor)

        self._kappa /= num_sampling_points

    def get_mode_heat_capacities(self):
        return self._cv

    def _run_at_grid_point(self):
        i = self._grid_point_count
        self._show_log_header(i)
        grid_point = self._grid_points[i]
        if not self._read_gamma:
            self._collision.set_grid_point(grid_point)
            
            if self._log_level:
                print "Number of triplets:",
                print len(self._pp.get_triplets_at_q()[0])
                print "Calculating interaction..."
                
            self._collision.run_interaction()
            self._set_gamma_at_sigmas(i)
            self._mean_square_pp_strength[i] = (
                self._pp.get_mean_square_strength())
            
        if self._isotope is not None and not self._read_gamma_iso:
            self._set_gamma_isotope_at_sigmas(i)

        self._cv[i] = self._get_cv(self._frequencies[grid_point])
        self._set_gv(i)
        
        if self._log_level:
            self._show_log(self._qpoints[i], i)

    def _allocate_values(self):
        num_band = self._primitive.get_number_of_atoms() * 3
        num_grid_points = len(self._grid_points)
        self._kappa = np.zeros((len(self._sigmas),
                                len(self._temperatures),
                                6), dtype='double')
        if not self._read_gamma:
            self._gamma = np.zeros((len(self._sigmas),
                                    len(self._temperatures),
                                    num_grid_points,
                                    num_band), dtype='double')
        self._gv = np.zeros((num_grid_points,
                             num_band,
                             3), dtype='double')
        self._cv = np.zeros((num_grid_points,
                             len(self._temperatures),
                             num_band), dtype='double')
        if self._isotope is not None:
            self._gamma_iso = np.zeros((len(self._sigmas),
                                        num_grid_points,
                                        num_band), dtype='double')
        self._mean_square_pp_strength = np.zeros((num_grid_points, num_band),
                                                 dtype='double')
        self._collision = ImagSelfEnergy(self._pp)
        
    def _set_gamma_at_sigmas(self, i):
        for j, sigma in enumerate(self._sigmas):
            if self._log_level:
                print "Calculating Gamma of ph-ph with",
                if sigma is None:
                    print "tetrahedron method"
                else:
                    print "sigma=%s" % sigma
            self._collision.set_sigma(sigma)
            if not sigma:
                self._collision.set_integration_weights()
            for k, t in enumerate(self._temperatures):
                self._collision.set_temperature(t)
                self._collision.run()
                self._gamma[j, k, i] = self._collision.get_imag_self_energy()
                
    def _get_gv_by_gv(self, i):
        rotation_map = get_grid_points_by_rotations(
            self._grid_address[self._grid_points[i]],
            self._point_operations,
            self._mesh)
        gv_by_gv = np.zeros((len(self._gv[i]), 3, 3), dtype='double')
        
        for r in self._rotations_cartesian:
            gvs_rot = np.dot(self._gv[i], r.T)
            gv_by_gv += [np.outer(r_gv, r_gv) for r_gv in gvs_rot]
        gv_by_gv /= len(rotation_map) / len(np.unique(rotation_map))
        order_kstar = len(np.unique(rotation_map))

        if order_kstar != self._grid_weights[i]:
            if self._log_level:
                print "*" * 33  + "Warning" + "*" * 33
                print (" Number of elements in k* is unequal "
                       "to number of equivalent grid-points.")
                print "*" * 73

        return gv_by_gv, order_kstar

    def _get_cv(self, freqs):
        cv = np.zeros((len(self._temperatures), len(freqs)), dtype='double')
        # T/freq has to be large enough to avoid divergence.
        # Otherwise just set 0.
        for i, f in enumerate(freqs):
            finite_t = (self._temperatures > f / 100)
            if f > self._cutoff_frequency:
                cv[:, i] = np.where(
                    finite_t, get_mode_cv(
                        np.where(finite_t, self._temperatures, 10000),
                        f * THzToEv), 0)
        return cv

    def _show_log(self, q, i):
        gp = self._grid_points[i]
        frequencies = self._frequencies[gp]
        gv = self._gv[i]
        mspp = self._mean_square_pp_strength[i]
        
        print "Frequency     group velocity (x, y, z)     |gv|     |mspp|",
        if self._gv_delta_q is None:
            print
        else:
            print " (dq=%3.1e)" % self._gv_delta_q

        if self._log_level > 1:
            rotation_map = get_grid_points_by_rotations(
                self._grid_address[gp],
                self._point_operations,
                self._mesh)
            for i, j in enumerate(np.unique(rotation_map)):
                for k, (rot, rot_c) in enumerate(zip(
                        self._point_operations, self._rotations_cartesian)):
                    if rotation_map[k] != j:
                        continue
    
                    print " k*%-2d (%5.2f %5.2f %5.2f)" % (
                        (i + 1,) + tuple(np.dot(rot, q)))
                    for f, v, pp in zip(frequencies,
                                    np.dot(rot_c, gv.T).T,
                                    mspp):
                        print "%8.3f   (%8.3f %8.3f %8.3f) %8.3f %11.3e" % (
                            f, v[0], v[1], v[2], np.linalg.norm(v), pp)
            print
        else:
            for f, v, pp in zip(frequencies, gv, mspp):
                print "%8.3f   (%8.3f %8.3f %8.3f) %8.3f %11.3e" % (
                    f, v[0], v[1], v[2], np.linalg.norm(v), pp)
    
