from pathlib import Path
import timeit
import fuzzyevaluation as fr

# ------------------------INPUT--------------------------------------
# Neighborhood definition
n = 4  # 'radius' of neighborhood
halving_distance = 2
comparison_name = "hexagon_fuzzynum_n4hd2_cubic"

# Create directory if not existent
current_dir = Path.cwd()
Path(current_dir / "rasters").mkdir(exist_ok=True)
map_A_in = str(current_dir / "rasters/hexagon/continuous_cubic/hexagon_sim_01_cubic.tif")
map_B_in = str(current_dir / "rasters/hexagon/continuous_cubic/hexagon_exp_01_cubic.tif")

# Save directory
Path(current_dir / "results").mkdir(exist_ok=True)
save_dir = str(current_dir/'results')
# ------------------------------------------------------------------

# Start run time count
start = timeit.default_timer()

# Perform fuzzy comparison
compareAB = fr.FuzzyComparison(map_A_in, map_B_in, n, halving_distance)
global_simil = compareAB.fuzzy_numerical(comparison_name, save_dir=save_dir)

# Print global similarity
print('Fuzzy measure [-]: ', global_simil)

# Stops run time count
stop = timeit.default_timer()

# Print run time:
print('Enlapsed time: ', stop - start, 's')
