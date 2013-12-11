.. RestfulGit documentation master file, created by
   sphinx-quickstart on Tue Dec 10 20:44:57 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to RestfulGit's documentation!
======================================

Contents:

.. toctree::
   :maxdepth: 2



API endpoints
=============
.. autoflask:: restfulgit:app
   :endpoints: restfulgit.get_commit_list
.. autoflask:: restfulgit:app
   :endpoints: restfulgit.get_commit
.. autoflask:: restfulgit:app
   :endpoints: restfulgit.get_blob
.. autoflask:: restfulgit:app
   :endpoints: restfulgit.get_tree
.. autoflask:: restfulgit:app
   :endpoints: restfulgit.get_tag
.. autoflask:: restfulgit:app
   :endpoints: restfulgit.get_ref_list
.. autoflask:: restfulgit:app
   :endpoints: restfulgit.get_raw
.. autoflask:: restfulgit:app
   :endpoints: restfulgit.get_repo_list
.. autoflask:: restfulgit:app
   :endpoints: restfulgit.get_description


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

