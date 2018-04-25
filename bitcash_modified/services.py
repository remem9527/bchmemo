import logging

import requests
from cashaddress import convert as cashaddress

from bitcash.network import currency_to_satoshi
from bitcash.network.meta import Unspent

from collections import OrderedDict

from datetime import datetime,timezone,date

DEFAULT_TIMEOUT = 30


def set_service_timeout(seconds):
    global DEFAULT_TIMEOUT
    DEFAULT_TIMEOUT = seconds

class InsightAPI:
    MAIN_ENDPOINT = ''
    # MAIN_ADDRESS_API = ''
    # MAIN_BALANCE_API = ''
    # MAIN_UNSPENT_API = ''
    # MAIN_TX_PUSH_API = ''
    # MAIN_TX_AMOUNT_API = ''
    # TX_PUSH_PARAM = ''

    MAIN_ADDRESS_API = 'addr/'
    MAIN_BALANCE_API = 'addr/{}/balance'
    MAIN_UNSPENT_API = 'addr/{}/utxo'
    MAIN_TX_PUSH_API = 'tx/send'
    MAIN_TX_API = 'tx/'
    MAIN_RAWTX_API='rawtx/'
    # MAIN_TXS_BY_ADDRESS_API= 'txs/?address='  # Only can return first 10 txs
    MAIN_TXS_BY_ADDRESSES_API='addrs/{}/txs?from={}&to={}'
    TX_PUSH_PARAM = 'rawtx'

    MAIN_TXS_BY_BLOCK='txs/?block={}&pageNum={}'
    MAIN_BLOCK_SUMMARIES_BY_DATE='blocks?blockDate={}'  # date: 2016-4-20

    MAIN_BLOCKHASH_BY_HEIGHT= 'block-index/'


    NEW_ADDRESS_SUPPORTED=True

    @classmethod
    def get_balance(cls, address):
        if not cls.NEW_ADDRESS_SUPPORTED:
            address = cashaddress.to_legacy_address(address)
        r = requests.get((cls.MAIN_ENDPOINT+cls.MAIN_BALANCE_API).format(address), timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:  # pragma: no cover
            raise ConnectionError
        return r.json()

    @classmethod
    def get_transactions(cls, address):
        """

        :param address:
        :return:list of transaction hash
        """
        if not cls.NEW_ADDRESS_SUPPORTED:
            address = cashaddress.to_legacy_address(address)
        r = requests.get(cls.MAIN_ENDPOINT+cls.MAIN_ADDRESS_API + address, timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:  # pragma: no cover
            raise ConnectionError
        return r.json()['transactions']

    @classmethod
    def get_tx_amount(cls, txid, txindex):
        r = requests.get(cls.MAIN_ENDPOINT+cls.MAIN_TX_API+txid, timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:  # pragma: no cover
            raise ConnectionError
        response = r.json()
        return response['vout'][txindex]['value']*100000000

    @classmethod
    def get_tx(cls, txid):
        r = requests.get(cls.MAIN_ENDPOINT+cls.MAIN_TX_API+txid, timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:  # pragma: no cover
            raise ConnectionError
        response = r.json()
        return response

    @classmethod
    def get_rawtx(cls, txid):
        r = requests.get(cls.MAIN_ENDPOINT+cls.MAIN_RAWTX_API+txid, timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:  # pragma: no cover
            raise ConnectionError
        response = r.json()
        return response['rawtx']

    @classmethod
    def get_unspent(cls, address):
        if not cls.NEW_ADDRESS_SUPPORTED:
            address = cashaddress.to_legacy_address(address)
        r = requests.get((cls.MAIN_ENDPOINT+cls.MAIN_UNSPENT_API).format(address), timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:  # pragma: no cover
            raise ConnectionError
        return [
            Unspent(currency_to_satoshi(tx['amount'], 'bch'),
                    tx['confirmations'],
                    tx['scriptPubKey'],
                    tx['txid'],
                    tx['vout'])
            for tx in r.json()
        ]

    @classmethod
    def broadcast_tx(cls, tx_hex):  # pragma: no cover
        r = requests.post(cls.MAIN_ENDPOINT+cls.MAIN_TX_PUSH_API, data={cls.TX_PUSH_PARAM: tx_hex}, timeout=DEFAULT_TIMEOUT)
        if r.status_code!=200:
            raise Exception(r.content)
        return True if r.status_code == 200 else False

    @classmethod
    def get_transactions_by_addresses(cls,addresses,start_index=0,stop_index=50):
        if stop_index-start_index>50:
            raise ValueError('Range between start_index ({}) and stop_index '
                             '({}) less than or equal to 50!'.format(start_index,stop_index))
        if isinstance(addresses,str):
            addresses=[addresses]
        if not cls.NEW_ADDRESS_SUPPORTED:
            addresses = [cashaddress.to_legacy_address(address) for address in addresses]
        addresses_str=','.join(addresses)

        r=requests.get((cls.MAIN_ENDPOINT + cls.MAIN_TXS_BY_ADDRESSES_API).
                       format(addresses_str,start_index,stop_index), timeout=DEFAULT_TIMEOUT)
        if r.status_code!=200:
            raise ConnectionError

        data=r.json()
        total_txs=data['totalItems']
        txs=data['items']   #type:list
        return total_txs,txs

    @classmethod
    def get_all_transactions_by_address(cls,address):
        """
        Get all txs related to an address
        :param address:
        :return:
        """
        total_txs,txs=cls.get_transactions_by_addresses(address)
        if total_txs<=50:
            return txs
        else:
            # if total_txs>50*10:
            #     raise TooManyTxs('Too many txs!')
            #     # todo: deal with too many txs
            start_indexes=list(range(50,total_txs,50))
            stop_indexes=list(range(100,total_txs,50))+[total_txs]
            for start_index,stop_index in zip(start_indexes,stop_indexes):
                total_txs, txs_follow_up = cls.get_transactions_by_addresses\
                    (address,start_index=start_index,stop_index=stop_index)
                txs=txs+txs_follow_up

            txs_id=[tx['txid'] for tx in txs]
            normal_dict=dict(zip(txs_id,txs))
            txs_id_no_duplicate=list(OrderedDict.fromkeys(txs_id).keys())  # remove duplicate txs
            txs_no_duplicate=[normal_dict[txid] for txid in txs_id_no_duplicate]
            return txs_no_duplicate

    @classmethod
    def get_transactions_by_address_from(cls,address,t):
        """
        Get all txs related to an address after t ,some tx after t may included
        :param address:
        :param timestap
        :return:
        """
        total_txs,txs=cls.get_transactions_by_addresses(address)
        if int(txs[-1]['time'])<t:
            return txs

        if total_txs<=50:
            return txs
        else:
            # if total_txs>50*10:
            #     raise TooManyTxs('Too many txs!')
            #     # todo: deal with too many txs
            start_indexes=list(range(50,total_txs,50))
            stop_indexes=list(range(100,total_txs,50))+[total_txs]
            for start_index,stop_index in zip(start_indexes,stop_indexes):
                total_txs, txs_follow_up = cls.get_transactions_by_addresses\
                    (address,start_index=start_index,stop_index=stop_index)
                txs=txs+txs_follow_up
                if int(txs[-1]['time']) < t:
                    break

            txs_id=[tx['txid'] for tx in txs]
            normal_dict=dict(zip(txs_id,txs))
            txs_id_no_duplicate=list(OrderedDict.fromkeys(txs_id).keys())  # remove duplicate txs
            txs_no_duplicate=[normal_dict[txid] for txid in txs_id_no_duplicate]
            return txs_no_duplicate

    @classmethod
    def get_transactions_by_block(cls,block_hash,page_num=0):
        r=requests.get((cls.MAIN_ENDPOINT+cls.MAIN_TXS_BY_BLOCK).format(block_hash,page_num),timeout=DEFAULT_TIMEOUT)
        if r.status_code!=200:
            raise  ConnectionError
        data=r.json()
        pages_total=int(data['pagesTotal'])
        txs=data['txs']  # type:list
        return pages_total,txs

    @classmethod
    def get_all_transactions_by_block(cls,block_hash):
        pages_total,txs=cls.get_transactions_by_block(block_hash,0)
        for i in range(1,pages_total):
            pt,txs_new=cls.get_transactions_by_block(block_hash,i)
            txs+=txs_new
        return txs

    @classmethod
    def get_block_summaries_by_date(cls,datestr=None):
        """

        :param datestr:2016-06-12
        :return:
        """
        if datestr is None:
            datestr=datetime.now().astimezone(timezone.utc).date().isoformat()
        
        r=requests.get((cls.MAIN_ENDPOINT+cls.MAIN_BLOCK_SUMMARIES_BY_DATE).format(datestr),timeout=DEFAULT_TIMEOUT)
        if r.status_code!=200:
            raise  ConnectionError
        data=r.json()
        block_summaries=data['blocks']
        return list(reversed(block_summaries))

    @ classmethod
    def get_block_summaries_by_from_to(cls,t_start,t_stop):
        """

        :param t_start: Unix timestamp
        :param t_stop:  Unix timestamp
        :return: block summaries that block time>=t_start and block.time<=t_stop
        """
        date_start=datetime.fromtimestamp(t_start,timezone.utc).date()
        date_stop=datetime.fromtimestamp(t_stop,timezone.utc).date()

        dates_ordinal_list=list(range(date_start.toordinal(),date_stop.toordinal()))+[(date_stop.toordinal())]
        dates=[date.fromordinal(day) for day in dates_ordinal_list]

        block_summaries=[]
        for day in dates:
            block_summaries+=cls.get_block_summaries_by_date(day.isoformat())

        block_summaries=[block_summary for block_summary in block_summaries
                         if int(block_summary['time'])>=t_start and int(block_summary['time']<=t_stop)]
        return block_summaries

    @classmethod
    def get_transactions_from_to(cls,t_start,t_stop):
        block_summaries=cls.get_block_summaries_by_from_to(t_start,t_stop)
        txs=[]
        for block in block_summaries:
            txs+=cls.get_all_transactions_by_block(block['hash'])
        return txs

    @classmethod
    def get_blockhash_by_heigth(cls,height):
        r=requests.get(cls.MAIN_ENDPOINT+ cls.MAIN_BLOCKHASH_BY_HEIGHT+str(height))
        if r.status_code!=200:
            raise  ConnectionError
        data=r.json()
        return data['blockHash']


class BCCBlockAPI(InsightAPI):
    """
    bccblock.info
    No testnet, sadly. Also uses legacy addresses only.
    """
    MAIN_ENDPOINT = 'https://bccblock.info/api/'
    # MAIN_ADDRESS_API = MAIN_ENDPOINT + 'addr/'
    # MAIN_BALANCE_API = MAIN_ADDRESS_API + '{}/balance'
    # MAIN_UNSPENT_API = MAIN_ADDRESS_API + '{}/utxo'
    # MAIN_TX_PUSH_API = MAIN_ENDPOINT + 'tx/send'
    # MAIN_TX_AMOUNT_API = MAIN_ENDPOINT + 'tx'
    # TX_PUSH_PARAM = 'rawtx'

    NEW_ADDRESS_SUPPORTED = False

    # @classmethod
    # def get_balance(cls, address):
    #     # As of 2018-02-02, bccblock.info only supports legacy addresses.
    #     address = cashaddress.to_legacy_address(address)
    #     r = requests.get(cls.MAIN_BALANCE_API.format(address), timeout=DEFAULT_TIMEOUT)
    #     if r.status_code != 200:  # pragma: no cover
    #         raise ConnectionError
    #     return r.json()

    # @classmethod
    # def get_transactions(cls, address):
    #     # As of 2018-02-02, bccblock.info only supports legacy addresses.
    #     address = cashaddress.to_legacy_address(address)
    #     r = requests.get(cls.MAIN_ADDRESS_API + address, timeout=DEFAULT_TIMEOUT)
    #     if r.status_code != 200:  # pragma: no cover
    #         raise ConnectionError
    #     return r.json()['transactions']

    # @classmethod
    # def get_unspent(cls, address):
    #     # As of 2018-02-02, bccblock.info only supports legacy addresses.
    #     address = cashaddress.to_legacy_address(address)
    #     r = requests.get(cls.MAIN_UNSPENT_API.format(address), timeout=DEFAULT_TIMEOUT)
    #     if r.status_code != 200:  # pragma: no cover
    #         raise ConnectionError
    #     return [
    #         Unspent(currency_to_satoshi(tx['amount'], 'bch'),
    #                 tx['confirmations'],
    #                 tx['scriptPubKey'],
    #                 tx['txid'],
    #                 tx['vout'])
    #         for tx in r.json()
    #     ]

class BlockdozerAPI(InsightAPI):
    MAIN_ENDPOINT = 'https://blockdozer.com/insight-api/'
    # MAIN_ADDRESS_API = MAIN_ENDPOINT + 'addr/'
    # MAIN_BALANCE_API = MAIN_ADDRESS_API + '{}/balance'
    # MAIN_UNSPENT_API = MAIN_ADDRESS_API + '{}/utxo'
    # MAIN_TX_PUSH_API = MAIN_ENDPOINT + 'tx/send'
    # MAIN_TX_AMOUNT_API = MAIN_ENDPOINT + 'tx'
    TEST_ENDPOINT = 'https://tbch.blockdozer.com/insight-api/'
    TEST_ADDRESS_API = TEST_ENDPOINT + 'addr/'
    TEST_BALANCE_API = TEST_ADDRESS_API + '{}/balance'
    TEST_UNSPENT_API = TEST_ADDRESS_API + '{}/utxo'
    TEST_TX_PUSH_API = TEST_ENDPOINT + 'tx/send'
    # TX_PUSH_PARAM = 'rawtx'

    NEW_ADDRESS_SUPPORTED = True

    @classmethod
    def get_balance_testnet(cls, address):
        r = requests.get(cls.TEST_BALANCE_API.format(address), timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:  # pragma: no cover
            raise ConnectionError
        return r.json()

    @classmethod
    def get_transactions_testnet(cls, address):
        r = requests.get(cls.TEST_ADDRESS_API + address, timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:  # pragma: no cover
            raise ConnectionError
        return r.json()['transactions']

    @classmethod
    def get_unspent_testnet(cls, address):
        r = requests.get(cls.TEST_UNSPENT_API.format(address), timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:  # pragma: no cover
            raise ConnectionError
        return [
            Unspent(currency_to_satoshi(tx['amount'], 'bch'),
                    tx['confirmations'],
                    tx['scriptPubKey'],
                    tx['txid'],
                    tx['vout'])
            for tx in r.json()
        ]

    @classmethod
    def broadcast_tx_testnet(cls, tx_hex):  # pragma: no cover
        r = requests.post(cls.TEST_TX_PUSH_API, data={cls.TX_PUSH_PARAM: tx_hex}, timeout=DEFAULT_TIMEOUT)
        if r.status_code == 200:
            return True
        else:
            logging.error(r.text)
            return False

class NetworkAPI:
    IGNORED_ERRORS = (ConnectionError,
                      requests.exceptions.ConnectionError,
                      requests.exceptions.Timeout,
                      requests.exceptions.ReadTimeout)

    GET_BALANCE_MAIN = [BCCBlockAPI.get_balance,
                        BlockdozerAPI.get_balance]
    GET_TRANSACTIONS_MAIN = [BCCBlockAPI.get_transactions,
                             BlockdozerAPI.get_transactions]
    GET_UNSPENT_MAIN = [BCCBlockAPI.get_unspent,
                        BlockdozerAPI.get_unspent]
    BROADCAST_TX_MAIN = [BCCBlockAPI.broadcast_tx,
                         BlockdozerAPI.broadcast_tx]
    GET_TX_MAIN= [BCCBlockAPI.get_tx,
                  BlockdozerAPI.get_tx]
    GET_RAWTX_MAIN= [BCCBlockAPI.get_rawtx,
                  BlockdozerAPI.get_rawtx]
    GET_TX_AMOUNT = [BCCBlockAPI.get_tx_amount,
                     BlockdozerAPI.get_tx_amount]
    GET_ALL_TXS_BY_ADDRESS=[BCCBlockAPI.get_all_transactions_by_address,
                        BlockdozerAPI.get_all_transactions_by_address]

    GET_TXS_BY_ADDRESSES=[BCCBlockAPI.get_transactions_by_addresses,
                          BlockdozerAPI.get_transactions_by_addresses]

    GET_TXS_BY_ADDRESS_FROM=[BCCBlockAPI.get_transactions_by_address_from,
                        BlockdozerAPI.get_transactions_by_address_from]

    BLOCKHASH_BY_HEIGHT=[BCCBlockAPI.get_blockhash_by_heigth,
                         BlockdozerAPI.get_blockhash_by_heigth]

    GET_BALANCE_TEST = [BlockdozerAPI.get_balance_testnet]
    GET_TRANSACTIONS_TEST = [BlockdozerAPI.get_transactions_testnet]
    GET_UNSPENT_TEST = [BlockdozerAPI.get_unspent_testnet]
    BROADCAST_TX_TEST = [BlockdozerAPI.broadcast_tx_testnet]

    @classmethod
    def get_balance(cls, address):
        """Gets the balance of an address in satoshi.

        :param address: The address in question.
        :type address: ``str``
        :raises ConnectionError: If all API services fail.
        :rtype: ``int``
        """

        for api_call in cls.GET_BALANCE_MAIN:
            try:
                return api_call(address)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def get_balance_testnet(cls, address):
        """Gets the balance of an address on the test network in satoshi.

        :param address: The address in question.
        :type address: ``str``
        :raises ConnectionError: If all API services fail.
        :rtype: ``int``
        """

        for api_call in cls.GET_BALANCE_TEST:
            try:
                return api_call(address)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def get_transactions(cls, address):
        """Gets the ID of all transactions related to an address.

        :param address: The address in question.
        :type address: ``str``
        :raises ConnectionError: If all API services fail.
        :rtype: ``list`` of ``str``
        """

        for api_call in cls.GET_TRANSACTIONS_MAIN:
            try:
                return api_call(address)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def get_transactions_testnet(cls, address):
        """Gets the ID of all transactions related to an address on the test
        network.

        :param address: The address in question.
        :type address: ``str``
        :raises ConnectionError: If all API services fail.
        :rtype: ``list`` of ``str``
        """

        for api_call in cls.GET_TRANSACTIONS_TEST:
            try:
                return api_call(address)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def get_tx_amount(cls, txid, txindex):
        """Gets the ID of all transactions related to an address.

        :param txid: The transaction id in question.
        :type txid: ``str``
        :param txindex: The transaction index in question.
        :type txindex: ``str``
        :raises ConnectionError: If all API services fail.
        :rtype: ``list`` of ``str``
        """

        for api_call in cls.GET_TX_AMOUNT:
            try:
                return api_call(txid, txindex)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def get_tx(cls, txid):
        """Gets tx dict by txid.

        :param txid: The transaction id in question.
        :type txid: ``str``
        :raises ConnectionError: If all API services fail.
        :rtype: ``dict``
        """

        for api_call in cls.GET_TX_MAIN:
            try:
                return api_call(txid)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def get_rawtx(cls, txid):
        """Gets rawtx by txid.

        :param txid: The transaction id in question.
        :type txid: ``str``
        :raises ConnectionError: If all API services fail.
        :rtype: ``str``
        """

        for api_call in cls.GET_RAWTX_MAIN:
            try:
                return api_call(txid)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def get_unspent(cls, address):
        """Gets all unspent transaction outputs belonging to an address.

        :param address: The address in question.
        :type address: ``str``
        :raises ConnectionError: If all API services fail.
        :rtype: ``list`` of :class:`~bitcash.network.meta.Unspent`
        """

        for api_call in cls.GET_UNSPENT_MAIN:
            try:
                return api_call(address)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def get_transactions_by_addresses(cls,addresses):
        """Gets latest 50 transactions in dict related to an address.

        :param addresses: bch addresse(s)
        :type addresses: ``str`` or ''list'' of ''str''
        :raises ConnectionError: If all API services fail.
        :rtype: ``list'' of ``dict``
        :return: All transactions in dict related to the address
        """

        for api_call in cls.GET_TXS_BY_ADDRESSES:
            try:
                return api_call(addresses)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def get_all_transactions_by_address(cls,address):
        """Gets all transactions in dict related to an address.

        :param address: bch address
        :type address: ``str``
        :raises ConnectionError: If all API services fail.
        :rtype: ``list'' of ``dict``
        :return: All transactions in dict related to the address
        """

        for api_call in cls.GET_ALL_TXS_BY_ADDRESS:
            try:
                return api_call(address)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def get_transactions_by_address_from(cls,address,t):
        """Gets all transactions in dict related to an address from time t

        :param address: bch address
        :type address: ``str``
        :raises ConnectionError: If all API services fail.
        :rtype: ``list'' of ``dict``
        :return: All transactions in dict related to the address
        """

        for api_call in cls.GET_TXS_BY_ADDRESS_FROM:
            try:
                return api_call(address,t)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def get_blockhash_by_height(cls,height):
        for api_call in cls.BLOCKHASH_BY_HEIGHT:
            try:
                return api_call(height)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')


    @classmethod
    def get_unspent_testnet(cls, address):
        """Gets all unspent transaction outputs belonging to an address on the
        test network.

        :param address: The address in question.
        :type address: ``str``
        :raises ConnectionError: If all API services fail.
        :rtype: ``list`` of :class:`~bitcash.network.meta.Unspent`
        """

        for api_call in cls.GET_UNSPENT_TEST:
            try:
                return api_call(address)
            except cls.IGNORED_ERRORS:
                pass

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def broadcast_tx(cls, tx_hex):  # pragma: no cover
        """Broadcasts a transaction to the blockchain.

        :param tx_hex: A signed transaction in hex form.
        :type tx_hex: ``str``
        :raises ConnectionError: If all API services fail.
        """
        success = None

        for api_call in cls.BROADCAST_TX_MAIN:
            try:
                success = api_call(tx_hex)
                if not success:
                    continue
                return
            except cls.IGNORED_ERRORS:
                pass

        if success is False:
            raise ConnectionError('Transaction broadcast failed, or '
                                  'Unspents were already used.')

        raise ConnectionError('All APIs are unreachable.')

    @classmethod
    def broadcast_tx_testnet(cls, tx_hex):  # pragma: no cover
        """Broadcasts a transaction to the test network's blockchain.

        :param tx_hex: A signed transaction in hex form.
        :type tx_hex: ``str``
        :raises ConnectionError: If all API services fail.
        """
        success = None

        for api_call in cls.BROADCAST_TX_TEST:
            try:
                success = api_call(tx_hex)
                if not success:
                    continue
                return
            except cls.IGNORED_ERRORS:
                pass

        if success is False:
            raise ConnectionError('Transaction broadcast failed, or '
                                  'Unspents were already used.')

        raise ConnectionError('All APIs are unreachable.')

class TooManyTxs(Exception):
    pass