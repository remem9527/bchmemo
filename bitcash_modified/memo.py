from datetime import datetime
import re

from bitcash.format import address_to_public_key_hash
from cashaddress.convert import Address
from cashaddress.convert import to_cash_address

from bchmemo.bitcash_modified.services import NetworkAPI

import bitcash.wallet
import bchmemo.bitcash_modified.transaction as transaction_modified

# modify objects related to transaction in bitcash.wallet
attr_to_be_modified='calc_txid, create_p2pkh_transaction, sanitize_tx_data, ' \
                    'OP_CHECKSIG, OP_DUP, OP_EQUALVERIFY, OP_HASH160, OP_PUSH_20'
attr_to_be_modified=re.split('\W+',attr_to_be_modified)
for attr in attr_to_be_modified:
    setattr(bitcash.wallet,attr,getattr(transaction_modified,attr))

# Parameters
PrivateKey=bitcash.wallet.PrivateKey

SUPPORTED_PREFIX=['6d01','6d02','6d04','6d06','6d07']
ACTION_NAME=['Set name','Post memo','Like / tip memo','Follow user','Unfollow user']
PRIFIX_BY_ACTION_NAME=dict(zip(ACTION_NAME,SUPPORTED_PREFIX))

USER_NAME_DICT={}

MIN_TRANSFER_FEE=1 # satoshi per Byte

class Memo:
    """
    This class represents a single memo and provides function including
    analyzing memo from a transaction and creating a transaction with memo.
    """

    def __init__(self):
        self.__action_name=None
        self.sender=''  # sender address
        self._prefix=None # hex string
        self._values= '' # hex string in OP_RETURN data except prefix and length bytes


        self._name=''
        self._message=''
        self._txhash_of_liked_memo= ''
        self._sender_of_liked_memo=''
        self.liked_memo=None
        self._tip_amount=0
        self._address=''  # hex string of public key hash

        self.transaction_hash=None
        self.transaction_dict=None
        self.transaction_time=None
        self.blockheight=None

        self.signed_transaction=None


        self.transfer=[]

    @classmethod
    def is_memo(cls,transaction:dict):
        """Return whether or not a transaction (dict format) is a memo transaction.

        :param  transaction: a dict format transaction
        :type transaction: dict

        """
        for vout in transaction['vout']:
            if vout['scriptPubKey']['hex'][0:2] == '6a' \
                    and vout['scriptPubKey']['hex'][4:8] in SUPPORTED_PREFIX:
                return True
        else:
            return False

    @classmethod
    def form_transaction_dict(cls, transaction):
        if not cls.is_memo(transaction):
            raise ValueError('Not valid transaction dict!')

        memo=Memo()
        memo.transaction_dict=transaction
        memo.transaction_hash=transaction['txid']
        memo.blockheight=transaction['blockheight']
        # memo.transaction_time=transaction['time']

        memo.__get_transfer()
        for vout in transaction['vout']:
            if vout['scriptPubKey']['hex'][0:2] == '6a' \
                    and vout['scriptPubKey']['hex'][4:8] in SUPPORTED_PREFIX:
                memo.prefix= vout['scriptPubKey']['hex'][4:8]
                memo.values= vout['scriptPubKey']['hex'][10:]
                break
        else:
            raise NotMemoTransaction('No OP_RETURN data in the transaction or none memo supported data.')

        addr_vin = []
        for vin in transaction['vin']:  # type:dict
            if 'addr' in vin:
                addr_vin.append(to_cash_address(vin['addr']))
        if len(addr_vin)>=1:
            memo.sender=addr_vin[0]

        memo.transaction_time=transaction['time']

        return memo

    def __get_transfer(self):
        """
        generate transfer form transaction dict
        """
        transfer=[]
        for vout in self.transaction_dict['vout']:
            if 'addresses' in vout['scriptPubKey']:
                transfer.append((to_cash_address(vout['scriptPubKey']['addresses'][0]),vout['value']))
        self.transfer=transfer

    @property
    def prefix(self):
        return self._prefix

    @prefix.setter
    def prefix(self,prefix):
        self._prefix=prefix
        try:
            index=SUPPORTED_PREFIX.index(prefix)
        except ValueError:
            raise ValueError('"{}" is not a supported memo prefix!',self._prefix)
        self.__action_name=ACTION_NAME[index]

    @property
    def values(self):
        return self._values

    @values.setter
    def values(self,value):
        """
            :param value: hex string in OP_RETURN data except prefix and length bytes
        """
        value_bytes=bytes.fromhex(value)
        if self._prefix==PRIFIX_BY_ACTION_NAME['Set name']:
            self.name=value_bytes.decode()
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Post memo']:
            self.message=value_bytes.decode()
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Like / tip memo']:
            self.txhash_of_liked_memo=value_bytes.hex()
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Follow user']:
            self.address=value_bytes.hex()
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Unfollow user']:
            self.address=value_bytes.hex()
        else:
            raise ValueError('"{}" is not a supported memo prefix!',self._prefix)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self,name):
        if not isinstance(name,str):
            raise TypeError('name should be a string!')
        if len(name)>75:
            raise ValueError('"{}" is too long.Max length of memo name is 75 bytes',name)
        else:
            self._name=name

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, message):
        if not isinstance(message,str):
            raise TypeError('message should be a string!')
        if len(message)>76:
            raise ValueError('"{}" is too long.Max length of memo message is 76 bytes',message)
        else:
            self._message=message

    @property
    def txhash_of_liked_memo(self):
        return self._txhash_of_liked_memo

    @txhash_of_liked_memo.setter
    def txhash_of_liked_memo(self, txhash):
        if not isinstance(txhash,str):
            raise TypeError('txhash should be a string!')
        if len(txhash)!=64:
            raise ValueError('txhash("{}") should be 64 bytes long'.format(txhash))
        else:
            self._txhash_of_liked_memo=bytes(reversed(bytes.fromhex(txhash))).hex()
            # self.__get_like_memo()

    @property
    def sender_of_liked_memo(self):
        return self._sender_of_liked_memo

    @sender_of_liked_memo.setter
    def sender_of_liked_memo(self,sender):
        self._sender_of_liked_memo=sender
        for addr, amount in self.transfer:
            if addr == sender:
                self._tip_amount += int(amount.replace('.',''))

    def __get_like_memo(self):
        """
        Get memo liked by this memo and calc tip amount
        """
        try:
            tx_like=NetworkAPI.get_tx(self._txhash_of_liked_memo)
        except:
            return
        if Memo.is_memo(tx_like):
            self.liked_memo=Memo.form_transaction_dict(tx_like)  # FIXME: Long runtime for multi-nesting like type memo
            for addr,amount in self.transfer:
                if addr==self.liked_memo.sender:
                    self._tip_amount+=int(float(amount) * 100000000)

    @property
    def address(self):
        return self._address

    @address.setter
    def address(self, address):
        if not isinstance(address,str):
            raise TypeError('address should be a string!')
        if len(address)!=40:
            raise ValueError('"{}" is not a public key hash',address)
        else:
            self._address=Address(payload=list(bytes.fromhex(address)),version= 'P2PKH').cash_address()

    def content(self):
        if self.sender and self._prefix and self._values:
            return 'EMPTY MEMO'

        line_sender=get_name_from_address(self.sender)+'@...'+self.sender[-6:]\
                    +' posted at '+datetime.fromtimestamp(int(self.transaction_time)).strftime('%Y-%m-%d %H:%M:%S')

        line_message=''
        if self._prefix==PRIFIX_BY_ACTION_NAME['Set name']:
            line_message= self.__action_name + ': ' + self.name
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Post memo']:
            line_message = self.__action_name + ': ' + self.message
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Like / tip memo']:
            line_message = self.__action_name + ': ' + self.txhash_of_liked_memo
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Follow user']:
            line_message = self.__action_name + ': ' + Address('P2PKH', list(bytes.fromhex(self.address))).cash_address()
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Unfollow user']:
            line_message = self.__action_name + ': ' + Address('P2PKH', list(bytes.fromhex(self.address))).cash_address()

        return line_sender+'\n'+line_message+'\n'

    def content_post(self):
        if self.prefix!=PRIFIX_BY_ACTION_NAME['Post memo']:
            raise TypeError('This is not a post memo!')

        line_sender = get_name_from_address(self.sender) + '@...' + self.sender[-6:] \
                      + ' posted at ' + datetime.fromtimestamp(int(self.transaction_time)).strftime('%Y-%m-%d %H:%M:%S')
        line_message = self.message

        return line_sender + '\n' + line_message + '\n'

    def content_like(self):
        if self.prefix!=PRIFIX_BY_ACTION_NAME['Like / tip memo']:
            raise TypeError('This is not a like / tip memo!')

        # if self.like_memo is None:
        #     presentation_of_liked_memo='Not a memo'
        # elif self.like_memo.sender=='':
        #     presentation_of_liked_memo='No sender address'
        # else:
        #     presentation_of_liked_memo=get_name_from_address(self.like_memo.sender)+'\'s post'
        #
        # line='Liked '\
        #      +presentation_of_liked_memo \
        #      +' ('+self.txhash+')'\
        #      +'- '+ '{0:,d}'.format(self._tip_aount) + ' satoshis' \
        #      +' at '+datetime.fromtimestamp(int(self.time)).strftime('%Y-%m-%d %H:%M:%S')

        line='Liked '\
             +' ('+self.txhash_of_liked_memo + ')'\
             +' at '+datetime.fromtimestamp(int(self.transaction_time)).strftime('%Y-%m-%d %H:%M:%S')

        return line

    def __create_values(self):
        """
        Create values hex string based on action type and action values.
        """
        if self._prefix==PRIFIX_BY_ACTION_NAME['Set name']:
            self._values=self.name.encode().hex()
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Post memo']:
            self._values=self.message.encode().hex()
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Like / tip memo']:
            self._values=self.txhash_of_liked_memo
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Follow user']:
            self._values=self.address
        elif self._prefix==PRIFIX_BY_ACTION_NAME['Unfollow user']:
            self._values=self.address

    @classmethod
    def set_name(cls,name,sender):
        memo=Memo()
        memo.sender=sender
        memo.prefix=PRIFIX_BY_ACTION_NAME['Set name']
        memo.name=name
        memo.__create_values()
        return memo

    @classmethod
    def post_memo(cls,message,sender):
        memo=Memo()
        memo.sender=sender
        memo.prefix=PRIFIX_BY_ACTION_NAME['Post memo']
        memo.message=message
        memo.__create_values()
        return memo

    @classmethod
    def like_memo(cls, liked_memo, sender, tip_amount=None, sender_of_liked_memo=None):
        """
        :type liked_memo: ``Memo``,  ``str``

        """

        memo=Memo()
        memo.sender=sender
        memo.prefix=PRIFIX_BY_ACTION_NAME['Like / tip memo']
        if isinstance(liked_memo,Memo):
            memo.liked_memo=liked_memo
            memo.txhash_of_liked_memo=memo.liked_memo.transaction_hash
            memo._sender_of_liked_memo=memo.liked_memo.sender
        elif isinstance(liked_memo,str):
            memo.txhash_of_liked_memo=liked_memo
            memo._sender_of_liked_memo=sender_of_liked_memo
        else:
            raise TypeError('Wrong liked_memo({}) type!'.format(liked_memo))
        memo.__create_values()

        if not isinstance(tip_amount,int) and tip_amount is not None:
            raise TypeError('tip_amount should be a string!')
        elif isinstance(tip_amount,int) and tip_amount<546:
            raise ValueError('Min transaction amount is 546')
        elif isinstance(tip_amount,int):
            memo._tip_amount=int(tip_amount)
            memo.__create_transfer()
        return memo

    def __create_transfer(self):
        if self._tip_amount!=0:
            self.transfer=[(self._sender_of_liked_memo, self._tip_amount, 'satoshi')]

    @classmethod
    def follow(cls,user_address,sender):
        memo=Memo()
        memo.sender=sender
        memo.prefix=PRIFIX_BY_ACTION_NAME['Follow user']
        memo.address=address_to_public_key_hash(user_address).hex()
        memo.__create_values()
        return memo

    @classmethod
    def unfollow(cls,user_address,sender):
        memo=Memo()
        memo.sender=sender
        memo.prefix=PRIFIX_BY_ACTION_NAME['Unfollow user']
        memo.address=address_to_public_key_hash(user_address).hex()
        memo.__create_values()
        return memo

    def create_signed_transaction(self,private_key,leftover=None):
        """

        :param private_key:
        :param leftover: address for receiving left bch. Default is sender.
        :return:
        """
        pk=PrivateKey(private_key)
        if pk.address != self.sender:
            raise ValueError('Wrong Private Key!')

        prefix_bytes=bytes.fromhex(self.prefix)
        len_prefix_bytes=len(prefix_bytes).to_bytes(1,byteorder='little')
        values_bytes=bytes.fromhex(self._values)
        len_values_bytes=len(values_bytes).to_bytes(1,byteorder='little')

        data_bytes=len_prefix_bytes+prefix_bytes+len_values_bytes+values_bytes

        pk.get_unspents()
        self.signed_transaction=pk.create_transaction(message=data_bytes,outputs=self.transfer,fee=MIN_TRANSFER_FEE,leftover=leftover)

        return self.signed_transaction

    def send_transaction(self):
        NetworkAPI.broadcast_tx(self.signed_transaction)
        return bitcash.wallet.calc_txid(self.signed_transaction)

    @classmethod
    def from_txhash(cls,txhash):
        tx_dict=NetworkAPI.get_tx(txhash)
        return Memo.form_transaction_dict(tx_dict)

class NotMemoTransaction(Exception):
    pass

def get_name_from_address(address):
    if address in USER_NAME_DICT:
        return USER_NAME_DICT[address]
    else:
        return address[-6:]