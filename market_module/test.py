from .tests.test_lib import defineArguments, processInput
from .short_term.tests.test_prototype_p2p import test_p2p
from .short_term.tests.test_prototype_p2p_co2 import test_p2p_co2
from .short_term.tests.test_prototype_p2p_distance import test_p2p_distance
from .short_term.tests.test_prototype_p2p_losses import test_p2p_losses
from .short_term.tests.test_prototype_pool import test_pool
from .short_term.tests.test_prototype_pool_networkdirections import test_pool_networkdir
from .short_term.tests.test_community import test_community_autonomy, test_community_peakshaving
from .long_term.tests.test_prototype_centralized import test_centralized

# Write Here all the available tests you want to run
availableTests = {
    "test:shortterm:pool": test_pool,
    "test:shortterm.pool:networkdir": test_pool_networkdir,
    "test:shortterm:p2p": test_p2p,
    "test:shortterm:p2p:co2": test_p2p_co2, 
    "test:shortterm:p2p:distance": test_p2p_distance, 
    "test:shortterm:p2p:losses": test_p2p_losses,
    "test:shortterm:community:autonomy": test_community_autonomy,
    "test:shortterm:community:peakshaving": test_community_peakshaving,
    "test:longterm:centralized": test_centralized
}


def init():
    # DO NOT CHANGE FROM THIS POINT BELOW
    # UNLESS YOU KNOW WHAT YOUR DOING
    args = defineArguments(availableTests)

    processInput(args, availableTests)
