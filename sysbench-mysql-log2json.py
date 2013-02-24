#!/usr/bin/python
# Copyright (C) 2011  Benoit Sigoure
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Parse sysbench's output and transform it into JSON."""

import simplejson as json
import os
import re
import sys


TOBYTES = {
  "K": 1024,
  "M": 1024 * 1024,
  "G": 1024 * 1024 * 1024,
  "T": 1024 * 1024 * 1024 * 1024,
}

TESTS = {
}

METRICS = (
#  ("num_threads", "Number of threads"),
#  ("test_mode", "Test mode"),
  ("nread", "Number of read queries"),
  ("nwrite", "Number of write queries"),
  ("nother", "Number of other queries"),
  ("ntotal", "Total number of queries"),
  ("transactions", "Transactions"),
  ("deadlocks", "Deadlocks"),
  ("rwrequests", "Total RW Requests"),
  ("otherrequests", " Total Other Requests"),
  ("total_time", "Total time"),
  ("total_num_events", "Total number of events"),
  #("total_exec_time", "Total execution time"),
  ("req_min", "Min. latency"),
  ("req_avg", "Avg. latency"),
  ("req_max", "Max. latency"),
  ("req_95p", "95th percentile latency"),
  # Derived metrics
  ("nreadps", "Reads/s"),
  ("nwriteps", "Writes/s"),
)

SORTED_METRICS = tuple(metric for metric, description in METRICS)
METRICS = dict(METRICS)

def tobytes(s):
  """Helper to convert, say, "1.42Mb" into `1488977.92'."""
  if "A" <= s[-2] <= "Z":
    return float(s[:-2]) * TOBYTES[s[-2]]
  return int(s[:-1])


def toms(s):
  """Helper to convert, say, "1.42s" into `1420'."""
  if s.endswith("ms"):
    return float(s[:-2])
  return float(s[:-1]) * 1000  # sec -> msec


def process(f, results):
  """Populate the results dict with data parsed from the file."""
  test_mode = num_threads = None
  resp_stats = query_stats = None

  data = None
  def record(metric, value):
    data[metric].setdefault(num_threads, []).append(value)

  line = None
  def match(regexp):
    m = re.match(regexp, line.strip())
    assert m, "%r did not match %r" % (line.strip(), regexp)
    return m

  for line in f:
    # Base case to start new section
    if line.endswith("run\n"):
      sysbench_args = dict(arg.lstrip("-").split("=", 1)
                           for arg in line.split()
                           if "=" in arg)
      num_threads = int(sysbench_args["num-threads"])
      test_mode = os.path.basename(sysbench_args["test"])
      resp_stats = False

      if test_mode not in TESTS:
        TESTS[test_mode] = test_mode

      if test_mode not in results:
        data = dict((metric, {}) for metric in METRICS)
        results[test_mode] = {
          "results": data,
        }
      else:
        data = results[test_mode]["results"]
    # Read until we get to the base case the first time
    elif test_mode is None:
      continue

    elif line == "    queries performed:\n":
      query_stats = True
    elif line == "    response time:\n":
      resp_stats = True

    elif query_stats and line.startswith("    transactions:"):
      transactions = int(line.split()[1])
      record("transactions", transactions)
    elif query_stats and line.startswith("    deadlocks:"):
      deadlocks = int(line.split()[1])
      record("deadlocks", deadlocks)
    elif query_stats and line.startswith("    read/write requests:"):
      requests = int(line.split()[2])
      record("rwrequests", requests)
    elif query_stats and line.startswith("    other operations:"):
      other = int(line.split()[2])
      record("otherrequests", other)
    elif line.startswith("    total time:"):
      total_time = toms(line.split()[-1])
      #record("total_time", total_time)
      total_time /= 1000
      record("nreadps", nread / total_time)
      record("nwriteps", nwrite / total_time)
    elif line.startswith("    total number of events:"):
      record("total_num_events", int(line.split()[-1]))
    #elif line.startswith("    total time taken by event execution:"):
    #  record("total_exec_time", float(line.split()[-1]))
    elif line == "\n":
      query_stats = False
      resp_stats = False

    elif query_stats and ": " in line:
      stat, value = line.split(":")
      stat = stat.strip()
      value = int(value.strip())
      if stat == "read":
        nread = value
        record("nread", value)
      elif stat == "write":
        nwrite = value
        record("nwrite", value)
      elif stat == "other":
        nother = value
        record("nother", value)
      elif stat == "total":
        ntotal = value
        record("ntotal", value)
      else:
        assert False, repr(stat)

    elif resp_stats and ": " in line:
      stat, value = line.split(":")
      stat = stat.strip()
      value = toms(value.strip())
      if stat == "min":
        record("req_min", value)
      elif stat == "avg":
        record("req_avg", value)
      elif stat == "max":
        record("req_max", value)
      elif stat == "approx.  95 percentile":
        record("req_95p", value)
      else:
        assert False, repr(stat)


def main(args):
  args.pop(0)
  if not args:
    print >>sys.stderr, "Need at least one file in argument"
    return 1
  # maps a config name to results for this config
  config2results = {}
  for arg in args:
    config = os.path.basename(os.path.dirname(arg))
    if not config:
      print >>sys.stderr, ("Error: %r needs to be in a directory named after"
                           " the config name" % (arg))
      return 2
    if config not in config2results:
      config2results[config] = {}
    f = open(arg)
    try:
      process(f, config2results[config])
    finally:
      f.close()

  for config, results in config2results.iteritems():
    for test_mode, data in results.iteritems():
      data["averages"] = dict((metric, [[num_threads, sum(vs) / len(vs)]
                                        for num_threads, vs in sorted(values.iteritems())])
                              for metric, values in data["results"].iteritems())
  f = open("results.js", "w")
  try:
    f.write("TESTS = ");
    json.dump(TESTS, f, indent=2)
    f.write(";\nMETRICS = {\n");
    f.write("\n".join('  "%s": "%s",' % (metric, METRICS[metric])
                      for metric in SORTED_METRICS))
    f.write("\n};\nresults = ");
    json.dump(config2results, f, indent=2)
    f.write(";")
  finally:
    f.close()


if __name__ == "__main__":
  sys.exit(main(sys.argv))
