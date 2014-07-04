import time
import signal
from datetime import timedelta, datetime

def backoff_wait(regular_poll_interval):
	if(backoff_wait.currWaitTime == 0):
		backoff_wait.currWaitTime = regular_poll_interval
	timeSinceLastWait = datetime.utcnow() - backoff_wait.lastEnteredWait
	if(timeSinceLastWait.total_seconds() >= backoff_wait.currWaitTime * 1.4):
		backoff_wait.currWaitTime = regular_poll_interval
	else:
		backoff_wait.currWaitTime = min(720, backoff_wait.currWaitTime * 2)
	
	backoff_wait.lastEnteredWait = datetime.utcnow()
	signal.signal(signal.SIGUSR1, passive_signal_handler)
	time.sleep(backoff_wait.currWaitTime)
	signal.signal(signal.SIGUSR1, signal.SIG_IGN)
backoff_wait.lastEnteredWait = datetime(1900, 1, 1)
backoff_wait.currWaitTime = 0

def passive_signal_handler(sigNum, stackFrame):
	pass