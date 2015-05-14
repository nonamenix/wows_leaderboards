#!/usr/bin/env python
# -*- coding: utf-8 -*-

import traceback
import logging
import gevent
from gevent import monkey, queue, event, pool


monkey.patch_all()

logging.basicConfig()


class Job(object):
    """Encapsulation of a job to put in the job queue.  Contains at least
    a URL, but can also have custom headers or entirely custom meta
    information.  The response object and data are tacked onto this object,
    which is then returned to the scraper for processing."""
    default_headers = {

    }

    def __init__(self, url, params={}, headers=None, meta=None, method='GET'):
        self.__url = url
        self.method = method
        self.params = params
        self.headers = dict(self.default_headers)
        self.headers.update(headers or {})
        self.meta = meta

    def __hash__(self):
        return hash("%s %s" % (self.url, frozenset(self.params.items())))

    def __cmp__(self, other):
        return cmp(hash(self), hash(other))

    def __repr__(self):
        return '<Job: %(method)s url=%(url)s, params=%(params)s, status=%(status)s%(extra)s>' % {
            'method': self.method,
            'url': self.url,
            'params': self.params,
            'status': 'done' if hasattr(self, 'response') else 'pending',
            'extra': ', code=%d, size=%d' % (
                self.response.status_code, len(self.response.text)
            ) if hasattr(self, 'response') else '',
        }

    url = property(lambda self: self.__url)


class Crawler(object):
    """Simple crawler based on gcrawler, but with a rolling inq that can be
    added to.  The crawler is done when the workers have no more jobs and
    there are no more urls in the queue."""
    seen_jobs = set()

    def __init__(self, spider, timeout=2, worker_count=4, pipeline_size=100):
        self.spider = spider
        self.spider.crawler = self
        self.timeout = timeout
        self.count = worker_count
        self.inq = queue.Queue(0)
        self.outq = queue.Queue(pipeline_size)
        self.jobq = queue.Queue()
        self.pool = pool.Pool(worker_count)
        self.worker_finished = event.Event()

        for job in getattr(self.spider, 'jobs', []):
            self.add_job(job)

        self.cache = '.cache'

    def start(self):
        """Start the crawler.  Starts the scheduler and pipeline first, then
        adds jobs to the pool and waits for the scheduler and pipeline to
        finish. The scheduler itself shuts down the pool and waits on that,
        so it's not required to watch the pool."""
        # add the spider's jobs first

        for url in self.spider.urls:
            self.add_job(url)
        # start the scheduler & the pipeline
        self.scheduler_greenlet = gevent.spawn(self.scheduler)
        self.pipeline_greenlet = gevent.spawn(self.pipeline)
        self.scheduler_greenlet.join()

    def add_job(self, job, **kwargs):
        """Add a job to the queue.  The job argument can either be a Job object
        or a url with keyword arguments to be passed to the Job constructor."""
        if isinstance(job, basestring):
            job = Job(job, **kwargs)
        # do not visit previously viewed urls

        if job in self.seen_jobs:
            return
        self.jobq.put(job)

    def scheduler(self):
        """A simple job scheduler.  Presuming it's started after there is at
        least one job, it feeds jobs to the job queue to a synchronous worker
        job queue one at a time.  When the worker queue fills up, the
        scheduler will block on the put() operation.  When job queue is empty,
        the scheduler will wait for the workers to finish.  If the job queue
        is empty and no workers are active, the pool's stopped."""
        logger = logging.getLogger(__name__ + '.scheduler')
        while True:
            # join dead greenlets
            for greenlet in list(self.pool):
                if greenlet.dead:
                    self.pool.discard(greenlet)
            try:
                logger.debug("Fetching job from job queue.")
                job = self.jobq.get_nowait()
            except queue.Empty:
                logger.debug("No jobs remaining.")
                if self.pool.free_count() != self.pool.size:
                    logger.debug("%d workers remaining, waiting..." % (self.pool.size - self.pool.free_count()))
                    self.worker_finished.wait()
                    self.worker_finished.clear()
                    continue
                else:
                    logger.debug("No workers left, shutting down.")
                    return self.shutdown()
            self.pool.spawn(self.worker, job)

    def shutdown(self):
        """Shutdown the crawler after the pool has finished."""
        self.pool.join()
        self.outq.put(StopIteration)
        self.pipeline_greenlet.join()
        return True

    def worker(self, job, logger=logging.getLogger(__name__ + '.worker')):
        """A simple worker that fetches urls based on jobs and puts the
        ammended jobs on the outq for processing in the pipeline thread.
        After each job is fetched, but before the worker sets the finished
        event, the spider's preprocess method will be called on the job. This
        is its opportunity to add urls to the job queue.  Heavy processing
        should be done via the pipeline in postprocess."""
        logger.debug("starting: %r" % job)
        # you need to create a new Http instance per greenlet, see ticket:
        # http://code.google.com/p/httplib2/issues/detail?id=5

        try:
            job.response = self.spider.session.request(
                job.method,
                job.url,
                params=job.params
            )
            self.spider.preprocess(job)
        except Exception, e:
            logger.error("Preprocessing error:\n%s" % traceback.format_exc())

        self.outq.put(job)
        self.worker_finished.set()
        logger.debug("finished: %r" % job)
        raise gevent.GreenletExit('success')

    def pipeline(self):
        """A post-processing pipeline greenlet which keeps post-processing from
        interfering with network wait parallelization of the worker pool."""
        logger = logging.getLogger(__name__ + '.pipeline')
        for job in self.outq:
            try:
                self.spider.postprocess(job)
            except:
                logger.error("error:\n%s" % traceback.format_exc())
        logger.debug("finished processing.")

        # def run(spider, **kwargs):
        # Crawler(spider, **kwargs).start()


class Spider(object):
    def __init__(self, urls=[], *args, **kwargs):
        self.urls = urls

    def preprocess(self, job):
        raise NotImplementedError

    def postprocess(self, job):
        raise NotImplementedError


