import time
import contextlib

from threading import Thread, Semaphore
from collections import defaultdict
from multiprocessing import Process

from redict import ValueProxy, Pool
from redict.proxy import _clear_all_locks

class Barrier(object):
    """
    This is about the same as python3's barrier primitive,
    but simulated using Semaphores.
    """
    def __init__(self, height):
        self.height, self.count = height, 0
        self.mutex, self.barrier = Semaphore(1), Semaphore(0)

    def wait(self):
        """Wait until the barrier height is reached"""
        self.mutex.acquire()
        self.count += 1
        self.mutex.release()

        if self.count == self.height:
            self.barrier.release()

        self.barrier.acquire()
        self.barrier.release()


@contextlib.contextmanager
def background_proc(target, args, jobs=1):
    """Start the callable target in `jobs` processes and pass `args` to it
    After those were started, execute the code in the with statement.
    """
    procs = []
    for _ in range(jobs):
        proc = Process(target=target, args=args)
        proc.start()
        procs.append(proc)

    yield

    for proc in procs:
        proc.join()


@contextlib.contextmanager
def background_thread(target, args, jobs=1):
    """Start the callable target in `jobs` threads and pass `args` to it.
    After those were started, execute the code in the with statement.
    """
    threads = []
    for _ in range(jobs):
        thr = Thread(target=target, args=args)
        thr.start()
        threads.append(thr)

    yield

    for thr in threads:
        thr.join()


def test_parallel_lock(real_redis):
    """Test if two processes really block on a common ressource"""
    val = ValueProxy('LockMe').set("x", 0)

    checks = defaultdict(bool)

    def _lock_me():
        """See if the thread could acquire the lock at last"""
        time.sleep(0.5)
        val.acquire()
        val.release()
        checks["thread-got-through"] = True

    jobs = 2
    with background_thread(_lock_me, (), jobs=jobs - 1):
        val.acquire()
        time.sleep(2)
        val.release()
        time.sleep(0.5)

    assert checks["thread-got-through"]


def test_parallel_proxy_sets(real_redis):
    """Test many parallel sets from more than one process."""

    ValueProxy(['QC']).set("x", 0)
    n_increments = 1000
    jobs = 4

    def _many_increments():
        """Make a lot of individually locked increments.
        In practice you should of course do the lock around the for loop
        to reduce lock contention, but here we want to trigger races.
        """
        # Note: Every process needs it's own lock.
        # Obvious, but easy to forget in unittests.
        proxy = ValueProxy(['QC'])
        for _ in range(n_increments):
            with proxy:
                proxy.set("x", proxy.get("x").val() + 1)

    with background_thread(_many_increments, (), jobs=jobs - 1):
        # This code runs in the foreground:
        _many_increments()

    # See if really all increments got counted.
    assert ValueProxy(['QC']).get("x").val() == jobs * n_increments

    # Reset and see if it also works for mutliple processes
    ValueProxy(['QC']).set("x", 0)
    with background_proc(_many_increments, (), jobs=jobs - 1):
        # This code runs in the foreground:
        _many_increments()

    # See if really all increments got counted.
    assert ValueProxy(['QC']).get("x").val() == jobs * n_increments


def test_alternative_db(real_redis):
    """Test if we can set different values for the same key in different
    redis databases. The actual redis db depends on the config.
    """
    Pool().reload(cfg={
        "names": {
            "snmp": 1,
            "img": 2,
        },
    })

    default_prox = ValueProxy("cache")
    default_prox.set("x", 0)

    snmp_prox = ValueProxy("cache", db_name="snmp")
    snmp_prox.set("x", 1)

    img_prox = ValueProxy("cache", db_name="img")
    img_prox.set("x", 2)

    assert default_prox.get("x").val() == 0
    assert snmp_prox.get("x").val() == 1
    assert img_prox.get("x").val() == 2

    not_prox = ValueProxy("cache", db_name="not_there")
    not_prox.set("x", 3)

    # Not existing db_names will land it db 0, same as default:
    assert default_prox.get("x").val() == 3
    assert not_prox.get("x").val() == 3


def test_many_open_connections(real_redis):
    """
    Test the connection pooling and see if we do not fail on too many.
    This test acquires 1000 open connections and runs some gets on it,
    to assert that the connection is actually being used.

    NOTE: This test assumes a high enough (> 1000) maxclients in redis.conf
    """
    prox = ValueProxy(
        ['ImageCache'],
        lock_acquire_timeout=100,
        lock_expire_timeout=105,
    )

    # Just set it to some dummy value.
    prox.set("url", "https://...")

    n_threads = 200
    barrier = Barrier(n_threads)

    def _use_me():
        """Helper function that does some dummy work"""
        # Wait for all threads to start.
        # We want to make sure the connection getting happens
        # at the same time for all threads.
        barrier.wait()

        for _ in range(100):
            assert prox["url"].exists()
            assert prox.val() == {"url": "https://..."}
            assert prox["url"].val() == "https://..."

    with background_thread(_use_me, (), jobs=n_threads-1):
        # Just use the main thread as one extra worker (thus -1)
        _use_me()


def test_recursive_lock_expire(real_redis):
    """Regression test for https://adnymics.atlassian.net/browse/DEV-1569:

    Sometimes locks somehow survived and had their expire time stripped.
    This was because release() set the value on a recursive lock, which
    stripped the expire time without setting it again.

    We test this as integration, because this error does not show
    when using fakeredis, only when using a real redis connection.
    """
    prox = ValueProxy(
        ['lock-test'],
        lock_acquire_timeout=10,
        lock_expire_timeout=15,
    )

    conn = Pool().get_connection()

    prox._redis_lock.acquire()
    prox._redis_lock.acquire()

    assert conn.ttl("l:.lock-test") == 15

    prox._redis_lock.release()

    assert conn.ttl("l:.lock-test") == 15
    time.sleep(1)
    assert conn.ttl("l:.lock-test") == 14

    prox._redis_lock.release()

    # The lock was cleared -> no key anymore -> negative ttl
    assert conn.ttl("l:.lock-test") < 0

