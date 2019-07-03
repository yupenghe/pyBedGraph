import random
import pyBigWig
import time
import numpy as np

EXACT_MEAN_INDEX = 0
APPROX_MEAN_INDEX = 1
MOD_APPROX_MEAN_INDEX = 2
RANDOM_SEED = 1

mean_names = [
    'pyBigWig_exact',
    'pyBigWig_approx',
    'pyBedGraph_exact',
    'pyBedGraph_approx',
    'pyBedGraph_mod_approx'
]

ALL_STATS = [
    "mean",
    "approx_mean",
    "mod_approx_mean",
    "max",
    "min",
    "coverage",
    "std"
]



class Benchmark:

    def __init__(self, bedGraph, bigWig_file):

        self.bw = pyBigWig.open(bigWig_file)
        self.bedGraph = bedGraph

        self.intervals_list = []

        self.num_tests = 0
        self.test_cases = None

        self.chromosome = None

    def benchmark(self, num_tests, interval_size, chrom_name, bin_size,
                  stats=None, only_runtime=False, bench_pyBigWig=True):

        # benchmark all stats if none given
        if stats is None:
            stats = ALL_STATS

        print("Benchmarking:\n"
              f"Number of tests: {num_tests}\n"
              f"Interval size: {interval_size}\n"
              f"Chromosome name: {chrom_name}\n"
              f"Bin size: {bin_size}\n"
              f"Stats to bench: {stats}\n"
              f"Only bench run time: {only_runtime}\n"
              f"Bench pyBigWig: {bench_pyBigWig}\n")

        # self.find_intervals()

        self.bedGraph.load_chrom_data(chrom_name)
        self.chromosome = self.bedGraph.chromosome_map[chrom_name]
        if bin_size is not None:
            self.chromosome.split_bins(bin_size)

        self.create_test_cases(num_tests, interval_size)

        results = {}
        actual = {}
        predictions = {}

        for stat_name in stats:

            results[stat_name] = {}

            if bench_pyBigWig:
                # actual value for approx_mean/mod_approx_mean is mean
                actual_stat_name = stat_name
                if 'mean' in stat_name and stat_name != 'mean':
                    actual_stat_name = 'mean'
                pyBigWig_name = 'pyBigWig_' + actual_stat_name

                if pyBigWig_name not in results:
                    results[pyBigWig_name] = {}

                # get actual value of the stat
                if actual_stat_name not in actual:
                    results[pyBigWig_name]['exact_run_time'], actual[actual_stat_name] = self.benchmark_pyBigWig(actual_stat_name)

                # get corresponding pyBigWig non-exact stat
                if pyBigWig_name not in predictions:
                    results[pyBigWig_name]['approx_run_time'], predictions[pyBigWig_name]\
                        = self.benchmark_pyBigWig(actual_stat_name, False)

            # get stat from pyBedGraph
            results[stat_name]['run_time'], predictions[stat_name] =\
                self.benchmark_self(stat_name)

        if only_runtime or not bench_pyBigWig:
            return results

        # find error
        for stat_name in predictions:
            actual_stat_name = stat_name
            if 'mean' in stat_name and stat_name != 'mean':
                actual_stat_name = 'mean'

            if 'pyBigWig_' in stat_name:
                actual_stat_name = stat_name[9:]  # get rid of the pyBigWig tag

            results[stat_name]['error'] = self.get_error(predictions[stat_name],
                                                         actual[actual_stat_name])

        return results

    def create_test_cases(self, num_tests, interval_size):

        random.seed(RANDOM_SEED)

        self.num_tests = num_tests
        test_cases = np.random.randint(2, self.chromosome.max_index, num_tests,
                                       dtype=np.int32)
        self.test_cases = np.vstack((test_cases, test_cases + interval_size))


    def find_intervals(self):

        self.intervals_list.clear()

        print("Finding intervals using pyBigWig's interval function...")
        start_time = time.time()

        for i in range(self.num_tests):
            intervals = self.bw.intervals(self.chromosome.name, self.test_cases[0][i], self.test_cases[1][i])
            self.intervals_list.append(intervals)

        time_taken = time.time() - start_time
        print(f"Time taken to get intervals: {time_taken} seconds")

    def benchmark_pyBigWig(self, stat, want_exact=True):

        if want_exact is False:
            print(f"Finding benchmark for pyBigWig's approximate {stat}...")
        else:
            print(f"Finding benchmark for pyBigWig's exact {stat}...")

        values = []
        start_time = time.time()
        for i in range(self.num_tests):
            value = self.bw.stats(self.chromosome.name, self.test_cases[0][i], self.test_cases[1][i],
                                   type=stat, exact=want_exact)
            values.append(value[0])
        time_taken = time.time() - start_time

        print(f"Time for {stat}: {time_taken} seconds for {self.num_tests} trials\n")
        return time_taken, values

    def benchmark_self(self, stat):

        print(f"Finding pyBedGraph benchmark for {stat}...")

        method = self.bedGraph.get_method(self.chromosome.name, stat)
        values = []

        start_time = time.time()
        for i in range(self.num_tests):
            value = method(self.test_cases[0][i], self.test_cases[1][i])
            values.append(value)
        time_taken = time.time() - start_time

        print(f"Time for {stat}: {time_taken} seconds for {self.num_tests} trials\n")
        return time_taken, values

    @staticmethod
    def get_error(predicted_values, actual_values):

        if len(predicted_values) != len(actual_values):
            print(f"Length of predicted values: {len(predicted_values)}, does"
                  f"not equal length of actual values: {len(actual_values)}")
            return

        percent_error_values = []
        for i in range(len(predicted_values)):
            actual = actual_values[i]
            predicted = predicted_values[i]

            if actual is None:
                actual = 0

            if predicted is None:
                predicted = 0

            if actual == 0 and predicted != 0:
                continue
            elif predicted == 0:
                percent_error_values.append(0)
            else:
                percent_error = abs(actual - predicted) / actual
                percent_error_values.append(percent_error)

        return np.mean(percent_error_values)