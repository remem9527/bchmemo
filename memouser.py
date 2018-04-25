from bitcash.wallet import PrivateKey
from cashaddress.convert import is_valid, to_cash_address

from bchmemo.bitcash_modified.services import NetworkAPI
from bchmemo.memo import Memo
from bchmemo.memo import PRIFIX_BY_ACTION_NAME
from bchmemo.memo import USER_NAME_DICT
from bchmemo.memo import get_name_from_address

PROMPT=True  # Prompt or not

class MemoUser:
    """
    This class represents  a memo user and provides functions about read and send memos

    :param address: the address of user
    :type address: ``str``

    """

    def __init__(self,address):
        if not isinstance(address,str):
            raise TypeError('address should be str!')
        if not is_valid(address):
            raise ValueError('{} is not a valid address'.format(address))

        self._address = to_cash_address(address)
        self.memos_send=[]  # list of memos sent by user
        self.memos_post=[]  # list of post memo sent by user
        self.memos_like=[]  # list of like / tip memo sent by user

        self.memos_receive=[]   # list of memos that are not sent by user but transfer BCH to user

        self._private_key=None

        self.name=None
        self.following=set()

    @classmethod
    def from_private_key(cls,private_key):
        """
        Return a memo user from private key.

        :param private_key:
        :type private_key: ``str`` or ``PrivateKey``
        :rtype ``MemoUser''
        """
        if not isinstance(private_key,PrivateKey):
            pk=PrivateKey(private_key)
        else:
            pk=private_key
        memouser=MemoUser(pk.address)
        memouser.private_key=pk.to_wif()
        return memouser

    def get_memos(self):
        """
        Get 1)memos sent by user, 2)memos that transfer BCH to user (tip memos to user)
        """
        total_txs,txs=NetworkAPI.get_transactions_by_addresses(self._address)
        memos=[Memo.form_transaction_dict(tx) for tx in txs if Memo.is_memo(tx)]
        self.memos_send=[memo for memo in memos if memo.sender==self._address]
        self.memos_receive=[memo for memo in memos if memo.sender!=self._address]

        self.memos_post=[memo for memo in self.memos_send if memo.prefix == PRIFIX_BY_ACTION_NAME['Post memo']]
        self.memos_like=[memo for memo in self.memos_send if memo.prefix == PRIFIX_BY_ACTION_NAME['Like / tip memo']]
        for memo in reversed(self.memos_send):
            if memo.prefix==PRIFIX_BY_ACTION_NAME['Set name']:
                self.name=memo.name
                USER_NAME_DICT[memo.sender]=memo.name
            if memo.prefix==PRIFIX_BY_ACTION_NAME['Follow user']:
                self.following.add(memo.address)
            if memo.prefix==PRIFIX_BY_ACTION_NAME['Unfollow user']:
                self.following.remove(memo.address)

    def get_memos_from(self,t):
        """

        """
        txs=NetworkAPI.get_transactions_by_address_from(self._address,t)
        memos=[Memo.form_transaction_dict(tx) for tx in txs if Memo.is_memo(tx)]
        self.memos_send=[memo for memo in memos if memo.sender==self._address]
        self.memos_receive=[memo for memo in memos if memo.sender!=self._address]

        self.memos_post=[memo for memo in self.memos_send if memo.prefix == PRIFIX_BY_ACTION_NAME['Post memo']]
        self.memos_like=[memo for memo in self.memos_send if memo.prefix == PRIFIX_BY_ACTION_NAME['Like / tip memo']]
        for memo in reversed(self.memos_send):
            if memo.prefix==PRIFIX_BY_ACTION_NAME['Set name']:
                self.name=memo.name
                USER_NAME_DICT[memo.sender]=memo.name
            if memo.prefix==PRIFIX_BY_ACTION_NAME['Follow user']:
                self.following.add(memo.address)
            if memo.prefix==PRIFIX_BY_ACTION_NAME['Unfollow user']:
                self.following.remove(memo.address)

    def list_posts(self):
        for memo in self.memos_post:
            print(memo.content_post())

    def list_likes(self):
        for memo in self.memos_like:
            print(memo.content_like())

    def list_following(self):
        print('following:')
        for addr in list(self.following):
            print(get_name_from_address(addr),addr)

    def list_memos(self):
        self.list_posts()
        self.list_likes()
        print()
        self.list_following()

    @property
    def private_key(self):
        return self._private_key

    @private_key.setter
    def private_key(self,private_key):
        pk=PrivateKey(private_key)
        if pk.address != self._address:
            raise ValueError('Wrong private key!')
        self._private_key=private_key

    def __send_new_memo(self,memo):
        memo.create_signed_transaction(self._private_key)
        txid=memo.send_transaction()
        if PROMPT:
            print('Successfully sent! txid={}'.format(txid))
            print('Check it on: https://explorer.bitcoin.com/bch/tx/{}'.format(txid))
        return txid

    def set_name(self, name):
        """
        :param name: no more than 76 bytes
        :type name: ``str``
        :return: transaction id
        """
        memo=Memo.set_name(name,self._address)
        return self.__send_new_memo(memo)

    def post_memo(self, message):
        """
        :param message: no more than 76 bytes
        :type message: ``str``
        :return: transaction id
        """
        memo=Memo.post_memo(message,self._address)
        return self.__send_new_memo(memo)

    def like_memo(self, liked_memo,tip_amount=None):
        memo=Memo.like_memo(liked_memo,self._address,tip_amount=tip_amount)

        return self.__send_new_memo(memo)

    def like_memo_tx(self, liked_memo, tip_amount=None, sender_of_liked_memo=None):
        """
        :param liked_memo: the memo or to tip or like, or, the transaction hash of that memo
        :type liked_memo: ``Memo`` or ``str``
        :param tip_amount: 0 for like, >546 for tip, in satoshi
        :type tip_amount: ``int``
        :param sender_of_liked_memo: sender's address of liked memo.If liked_memo is transaction
                    hash and this is None, this need be get from NetworkAPI
        :type sender_of_liked_memo: ``str``
        :return:
        """
        if isinstance(liked_memo,Memo):
            memo = Memo.like_memo(liked_memo, self._address, tip_amount=tip_amount)
        elif isinstance(liked_memo,str):
            if sender_of_liked_memo is None:
                liked_memo=Memo.from_txhash(liked_memo)
                memo = Memo.like_memo(liked_memo, self._address, tip_amount=tip_amount)
            else:
                memo = Memo.like_memo(liked_memo, self._address, tip_amount=tip_amount, sender_of_liked_memo=sender_of_liked_memo)
        else:
            raise TypeError('liked_memo should be Memo object or string!')

        return self.__send_new_memo(memo)

    def follow(self, address):
        """
        :param address:
        :type address: ``str``
        :return: transaction id
        """

        memo=Memo.follow(address,self._address)
        return self.__send_new_memo(memo)

    def unfollow(self, address):
        """
        :param address: no more than 76 bytes
        :type address: ``str``
        :return: transaction id
        """
        memo=Memo.unfollow(address,self._address)
        return self.__send_new_memo(memo)

class UnknownPrivateKey(Exception):
    pass
