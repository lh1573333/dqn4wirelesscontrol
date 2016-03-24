import numpy as np
import pandas as pd
import json


class TrafficServer:
    """Emulates the data plane of a communication system

    TrafficServer can provide certain service for the traffic generated by a TrafficEmulator. It is essentially the
    data-plane of a communication system, and decide service under the instruction of the control-plane - Controller.

    To use it, first feed it with some traffic and wait it to update its internal state, then make observation from it
    and propagate it to the controller, who will issue specific control commands. Using these control commands, one can
    get services for the traffic fed, and also receive a operational cost at the same time.

    Note all functions are not necessarily fully controlled by the controller, and the TrafficServer may have some
    sovereign over miscellaneous functions and only leave the most important parts for the Controller to decide. To this
    regard, the TrafficServer can have some hidden state that is not observable by the controller.

    A important implementation feature in our current project is to give TrafficServer the ability to sleep and queue
    requests. These operational states are reflected in both the service generated and the cost emitted.
    """
    def __init__(self, verbose=0):
        self.epoch = None
        self.current_traffic = None
        self.q = None
        self.reset()
        self.verbose = verbose      # verbosity level

    # Public Methods
    def observe(self, traffic_df):
        """Compile observation from current traffic and queue
        Observe from traffic and queue, then compile a summary as information.
        """
        if traffic_df is None:
            raise ValueError("Please feed traffic.")
        self.current_traffic = traffic_df
        traffic_observation = self.observe_traffic_()
        q_observation = self.observe_q_()
        return traffic_observation, q_observation

    def get_service_and_cost(self, control):
        """Generate service based on the control commands
        """

        sleep_flag, control_req = control  # extract control commands
        self.enqueue_all_traffic_()  # put all incoming requests into queue first
        # if server sleep in the current round,
        if sleep_flag:
            service = pd.DataFrame(columns=['sessionID', 'service_per_request_per_domain'])
            cost = 0  # set cost=0
        # else...
        else:
            service = self.serve_requests_(control_req)
            cost = 1  # set cost=1
        # Prepare for next epoch
        self.current_traffic = None  # clear traffic buffer
        self.epoch += 1
        return service, cost

    def reset(self):
        self.epoch = 0
        self.current_traffic = None
        self.q = pd.DataFrame(columns=['sessionID', 'uid', 'arriveTime_epoch', 'bytesSent_per_request_per_domain'])

    # Private Methods
    def observe_traffic_(self):
        """Summary information from current traffic
        Currently the total number of requests and bytes (tuple)
        """
        num_req = 0
        num_bytes = 0
        for idx in self.current_traffic.index:
            bytesSent_req_domain = json.loads(self.current_traffic.loc[idx, 'bytesSent_per_request_per_domain'])
            num_req += sum([len(bytesSent_req_domain[domain]) for domain in bytesSent_req_domain])
            num_bytes += sum([bytesSent_req_domain[domain][reqID]
                              for domain in bytesSent_req_domain for reqID in bytesSent_req_domain[domain]])
        return num_req, num_bytes

    def observe_q_(self):
        """Summary queue state for observation

        Currently the summary is the # of requests left in to queue
        :return: queue observation
        """
        q_len = 0
        for idx in self.q.index:
            bytesSent_req_domain = json.loads(self.q.loc[idx, 'bytesSent_per_request_per_domain'])
            q_len += sum([len(bytesSent_req_domain[domain]) for domain in bytesSent_req_domain])
        return q_len

    def enqueue_all_traffic_(self):
        enq_df = self.current_traffic
        enq_df['arriveTime_epoch'] = self.epoch
        self.q = self.q.append(enq_df, ignore_index=True)
        return

    def dequeue_all_traffic_(self):
        q = self.q
        self.q = pd.DataFrame(columns=['sessionID', 'uid', 'arriveTime_epoch' 'bytesSent_per_request_per_domain'])
        return q

    def serve_requests_(self, control_req):
        """Serve queued requests.

        :param control_req:
        :return:
        """
        service_df = pd.DataFrame(columns=['sessionID', 'service_per_request_per_domain'])
        service_str = control_req  # service command for queued and incoming requests
        q = None

        # 1. serve all queued requests
        if service_str == 'serve_all':
            q = self.dequeue_all_traffic_()  # deque all queued traffic
            for idx in q.index:  # for each traffic entry
                sessionID = int(q.loc[idx, 'sessionID'])
                bytesSent_req_domain = json.loads(q.loc[idx, 'bytesSent_per_request_per_domain'])

                # register service for each request
                service_req_domain = {}
                for domain in bytesSent_req_domain:  # for each domain in the entry
                    for reqID in bytesSent_req_domain[domain]:  # for each request under the domain
                        # register 'serve' to the service
                        if domain not in service_req_domain:
                            service_req_domain[domain] = {}
                        service_req_domain[domain][reqID] = 'serve'
                q.loc[idx, 'service_per_request_per_domain'] = json.dumps(service_req_domain)

                # if multiple entries with same sessionID exist, merge into one entry
                idx_old = (int(sessionID) == q['sessionID']).nonzero()[0][0]
                if idx != idx_old:
                    service_req_domain_old = json.loads(q.loc[idx_old, 'service_per_request_per_domain'])
                    for domain in service_req_domain:
                        for reqID in service_req_domain[domain]:
                            if domain not in service_req_domain_old:
                                service_req_domain_old[domain] = {}
                            if reqID not in service_req_domain_old[domain]:
                                service_req_domain_old[domain][reqID] = service_req_domain[domain][reqID]
                    q.loc[idx_old, 'service_per_request_per_domain'] = json.dumps(service_req_domain_old)
                    q.drop([idx], inplace=True)

            if self.verbose > 0:
                print "TrafficServer.__serve_requests__(): serving all requests in queue."

        # 2. keep all requests in queue
        elif service_str == 'queue_all':
            q = self.q.copy()
            for idx in q.index:
                sessionID = int(q.loc[idx, 'sessionID'])
                bytesSent_req_domain = json.loads(q.loc[idx, 'bytesSent_per_request_per_domain'])

                # register service for each request
                service_req_domain = {}
                for domain in bytesSent_req_domain:
                    for reqID in bytesSent_req_domain[domain]:
                        if domain not in service_req_domain:
                            service_req_domain[domain] = {}
                        service_req_domain[domain][reqID] = 'queue'
                q.loc[idx, 'service_per_request_per_domain'] = json.dumps(service_req_domain)

                # if multiple entries with same sessionID exist, merge into one entry
                idx_old = (int(sessionID) == q['sessionID']).nonzero()[0][0]
                if idx != idx_old:
                    service_req_domain_old = json.loads(q.loc[idx_old, 'service_per_request_per_domain'])
                    for domain in service_req_domain:
                        for reqID in service_req_domain[domain]:
                            if domain not in service_req_domain_old:
                                service_req_domain_old[domain] = {}
                            service_req_domain_old[domain][reqID] = service_req_domain[domain][reqID]
                    q.loc[idx_old, 'service_per_request_per_domain'] = json.dumps(service_req_domain_old)
                    q.drop([idx], inplace=True)

            if self.verbose > 0:
                print "TrafficServer.__serve_requests__(): queuing all requests in queue."

        # 3. randomly serve or keep queuing requests
        elif service_str == 'random_serve_and_queue':
            q = self.q.copy()
            num_serve = 0
            num_queue = 0
            for idx in q.index:
                sessionID = int(q.loc[idx, 'sessionID'])
                bytesSent_req_domain = json.loads(q.loc[idx, 'bytesSent_per_request_per_domain'])

                # if multiple entries with same sessionID exist, merge into one entry
                service_req_domain = {}
                for domain in bytesSent_req_domain:
                    for reqID in bytesSent_req_domain[domain]:
                        if domain not in service_req_domain:
                            service_req_domain[domain] = {}
                        r = np.random.rand()
                        if r < 0.5:
                            service_req_domain[domain][reqID] = 'serve'
                            num_serve += 1
                            bytesSent_req_domain[domain][reqID] = None
                        else:
                            service_req_domain[domain][reqID] = 'queue'
                            num_queue += 1
                    bytesSent_req_domain[domain] = dict((k, v) for k, v in bytesSent_req_domain[domain].iteritems() if v)
                    if len(bytesSent_req_domain[domain]) == 0:
                        bytesSent_req_domain[domain] = None
                bytesSent_req_domain = dict((k, v) for k, v in bytesSent_req_domain.iteritems() if v)
                q.loc[idx, 'service_per_request_per_domain'] = json.dumps(service_req_domain)
                if len(bytesSent_req_domain) == 0:
                    self.q.drop([idx], inplace=True)
                else:
                    self.q.loc[idx, 'bytesSent_req_domain'] = json.dumps(bytesSent_req_domain)

                # if multiple entries with same sessionID exist, merge into one entry
                idx_old = (int(sessionID) == q['sessionID']).nonzero()[0][0]
                if idx != idx_old:
                    service_req_domain_old = json.loads(q.loc[idx_old, 'service_per_request_per_domain'])
                    for domain in service_req_domain:
                        for reqID in service_req_domain[domain]:
                            if domain not in service_req_domain_old:
                                service_req_domain_old[domain] = {}
                            service_req_domain_old[domain][reqID] = service_req_domain[domain][reqID]
                    q.loc[idx_old, 'service_per_request_per_domain'] = json.dumps(service_req_domain_old)
                    q.drop([idx], inplace=True)

            if self.verbose > 0:
                print "TrafficServer.__serve_requests__(): serving {} request and queueing {} requests.".format(num_serve, num_queue)
        else:
            if self.verbose > 0:
                print "TrafficServer.__serve_requests__(): no control received, return empty service_df."

        if q is not None:
            service_df = pd.concat([service_df, q], axis=0, join='inner', ignore_index=True)

        return service_df
