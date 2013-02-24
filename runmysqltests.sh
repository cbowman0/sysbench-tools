#!/bin/bash

#set -u
#set -x

#sysbench arguments
#http://www.percona.com/docs/wiki/benchmark:sysbench:olpt.lua
SYSBENCH_TESTS_DEFAULT_ARGS=" _SYSBENCH_ \
    --test=_TESTDIR_/_TEST_ \
    --oltp-table-size=_TABLESIZE_ \
    --oltp-tables-count=_NUMTABLES_ \
    --max-time=300 \
    --max-requests=0 \
    --mysql-user=_USER_ \
    --mysql-password=_PASS_ \
    --mysql-host=_DBHOST_ \
    --mysql-db=_DBNAME_ \
    --mysql-table-engine=InnoDB \
    --mysql-engine-trx=yes \
    --num-threads=_NUMTHREAD_ "

SYSBENCH_TESTS="delete.luai insert.lua oltp.lua select.lua select_random_points.lua select_random_ranges.lua update_index.lua update_non_index.lua"


usage()
{
cat << EOF
usage: $0 options

Perform the sysbench test against MySQL.  Runs the following db tests:
$SYSBENCH_TESTS

OPTIONS:
   -h      Show this message
   -s      Database Host
   -d      Database Name
   -u      User in Database
   -p      Password of Database User
   -i      Size of tables
   -n      Number of tables
   -t      Test Name
   -o      Output Directory
   -v      Verbose
EOF
}

DBHOST=
DBNAME="sbtest"
DBUSER="sbtest"
DBPASS="sbtest1"
TABLESIZE=2000000
NUMTABLES=8
TESTNAME=
VERBOSE=0

# Path to sysbench
SYSBENCH=../sysbench/sysbench/sysbench
SYSBENCH_DB_TESTS=../sysbench/sysbench/tests/db/
OUTDIR=

while getopts “hs:d:u:p:i:n:t:v” OPTION
do
     case $OPTION in
         h)
             usage
             exit 1
             ;;
         s)
             DBHOST=$OPTARG
             ;;
         d)
             DBNAME=$OPTARG
             ;;
         u)
             DBUSER=$OPTARG
             ;;
         p)
             DBPASS=$OPTARG
             ;;
         i)
             TABLESIZE=$OPTARG
             ;;
         n)
             NUMTABLES=$OPTARG
             ;;
         t)
             TESTNAME=$OPTARG
             ;;
         o)
             OUTDIR=$OPTARG
             ;;
         v)
             VERBOSE=1
             ;;
         ?)
             usage
             exit
             ;;
     esac
done

if [[ -z $DBHOST ]] || [[ -z $TESTNAME ]] || [[ -z $OUTDIR ]]
then
     usage
     exit 1
fi


# No spaces in name
TEST_NAME="$TESTNAME-TableSize-$TABLESIZE-Tables-$NUMTABLES"

NUMTHREADS="1 4 8 16 32 64 128"
NUMITERATIONS="1 2 3 4"

#Set start date?
# date +%Y%m%d%H%M%S

for SBTEST in $SYSBENCH_TESTS; do
  for NUMTHREAD in $NUMTHREADS; do
    TEST_EXEC="$SYSBENCH_TESTS_DEFAULT_ARGS"
    mkdir -p $OUTDIR/$TEST_NAME
    exec >$OUTDIR/$TEST_NAME/$SBTEST-$NUMTHREAD 2<&1
    echo "`date` TESTING $TEST_NAME-$SBTEST-$NUMTHREAD"

    #Perform _VARIABLE_ substitutions
    TEST_EXEC=${TEST_EXEC/_SYSBENCH_/$SYSBENCH}
    TEST_EXEC=${TEST_EXEC/_TESTDIR_/$SYSBENCH_DB_TESTS}
    TEST_EXEC=${TEST_EXEC/_USER_/$DBUSER}
    TEST_EXEC=${TEST_EXEC/_PASS_/$DBPASS}
    TEST_EXEC=${TEST_EXEC/_DBHOST_/$DBHOST}
    TEST_EXEC=${TEST_EXEC/_DBNAME_/$DBNAME}
    TEST_EXEC=${TEST_EXEC/_TABLESIZE_/$TABLESIZE}
    TEST_EXEC=${TEST_EXEC/_NUMTABLES_/$NUMTABLES}

    PREPARE_EXEC="$TEST_EXEC"

    for i in $NUMITERATIONS; do
      echo "`date` start iteration $i"
      P=${PREPARE_EXEC/_TEST_/parallel_prepare.lua}
      P=${P/_NUMTHREAD_/$NUMTHREAD}
      echo $P run
      $P run
      T=${TEST_EXEC/_TEST_/$SBTEST}
      T=${T/_NUMTHREAD_/$NUMTHREAD}
      echo $T run
      $T run
      $P cleanup
    done
    echo "`date` DONE TESTING $TEST_NAME-$SBTEST-$NUMTHREAD"
    sleep 30
  done
  # date | mail -s "$mode benchmarks done" your@email.here
done
