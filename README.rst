Memo
=======================
A python package for memo. Memo is  an on-chain social network built on Bitcoin Cash

Based on `bitcash`_.


How to use
------------------

.. code-block:: python

    >>> user = MemoUser('bitcoincash:qqplzy4l2uxzwa5k3zc2mftkw3q6340a4cfy4kd3nf')
    >>> user.private_key = 'PRIVATEKEY'

    >>> user.set_name('Test User For Python Package')
    Successfully sent! txid=d8c9d05ffefd5211353b3ef7b47ede424d3b78f7f1a4911d5d8792ae35072c04
    Check it on: https://explorer.bitcoin.com/bch/tx/txid=d8c9d05ffefd5211353b3ef7b47ede424d3b78f7f1a4911d5d8792ae35072c04

    >>>user.post_memo('First memo from python package!')
    Successfully sent! txid=1f84551778197aae7ea82dced737d4ef644b9517e91cc867a354a1aad55f9b09
    Check it on: https://explorer.bitcoin.com/bch/tx/1f84551778197aae7ea82dced737d4ef644b9517e91cc867a354a1aad55f9b09

    >>>user.follow('bitcoincash:qzdxp2z5yuxzlskafh2d8wsq7grg7rt46csg3qcn80')
    Successfully sent! txid=8d95e27eb1df5c4d97446fda69baab3fa7df568131252d2685d7c3203c366fe1
    Check it on: https://explorer.bitcoin.com/bch/tx/8d95e27eb1df5c4d97446fda69baab3fa7df568131252d2685d7c3203c366fe1

    >>>user.like_memo('f0e24cbeb7d5cebc1577d76385892c0f28d50d34f24729981617c64441329de5')
    Successfully sent! txid=262fd91e68381e1d32a6b5d93b8d672d12117588efadaa02e603aaf6253728ee
    Check it on: https://explorer.bitcoin.com/bch/tx/262fd91e68381e1d32a6b5d93b8d672d12117588efadaa02e603aaf6253728ee

    >>>user.get_memos()
    >>>user.list_memos()
    Test User For Python Package@...4kd3nf posted at 2018-04-25 02:31:49
    First memo from python package!

    Liked  (f0e24cbeb7d5cebc1577d76385892c0f28d50d34f24729981617c64441329de5) at 2018-04-25 02:31:49

    following:
    3qcn80 bitcoincash:qzdxp2z5yuxzlskafh2d8wsq7grg7rt46csg3qcn80

If you want to generate private keys, you can use `bitcash`_ from sporestack

Installation
------------


.. code-block:: bash

    $ pip install bchmemo


Credits
-------

- `sporestack`_ for the bitcash

.. _sporestack: https://github.com/sporestack/bitcash
.. _bitcash: https://github.com/sporestack/bitcash
