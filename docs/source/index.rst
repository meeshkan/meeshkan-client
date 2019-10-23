.. meeshkan documentation master file, created by
   sphinx-quickstart on Mon Jan 14 12:44:49 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=======================================================================
Meeshkan - Monitoring and remote-control tool for machine learning jobs
=======================================================================

**NOTICE: The package has been deprecated.**

``meeshkan`` is a Python package providing control to your machine learning jobs.

Main Features
-------------

Here are just a few of the things ``meeshkan`` can do:

  - Notify you of your job's progress at fixed intervals.
  - Notify you when certain events happen
  - Schedule machine learning jobs for execution
  - Allow you to control training jobs remotely
  - Allow monitoring Amazon SageMaker jobs

.. include:: ./quick-start.rst

===================
Meeshkan Python API
===================

.. automodule:: meeshkan
   :members:
   :undoc-members:

.. automodule:: meeshkan.sagemaker
   :members:
   :undoc-members:

======================
Command-line interface
======================

.. click:: meeshkan.__main__:cli
   :prog: meeshkan
   :show-nested:
