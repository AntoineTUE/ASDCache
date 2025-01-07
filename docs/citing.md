# Citing and Acknowledging

When using `readASD` in your research or work in general, please make sure to cite the following works, using the appropriate citation format and conventions.

First and foremost, cite the [NIST Atomic Spectra Database](https://www.nist.gov/pml/atomic-spectra-database) that curates and publishes the relevant data.

They have a recommended citation format on a [dedicated page](https://physics.nist.gov/PhysRefData/ASD/Html/verhist.shtml), with relevant version history information.

Below is a summary of these, but be sure to update the version information if necessary.

=== "NIST ASD citation"
    !!! quote "Citation"
        Kramida, A., Ralchenko, Yu., Reader, J. and [NIST ASD Team](https://physics.nist.gov/PhysRefData/ASD/index.html#Team) (2024). *NIST Atomic Spectra Database* (version 5.12), [Online]. Available: https://physics.nist.gov/asd [Thu Dec 12 2024]. National Institute of Standards and Technology, Gaithersburg, MD. DOI: https://doi.org/10.18434/T4W30F

=== "Recommended format"
    !!! quote "Citation style"
        Author(s)/editor(s) (Year). Title (edition), [Type of medium]. Available: URL [Access date].

=== "BibTeX"
    ```bibtex
    @dataset{Kramida2024NISTASD,
        doi = {10.18434/T4W30F},
        url = {https://physics.nist.gov/asd},
        author = {Kramida,  Alexander and Ralchenko,  Yuri and Reader, Joseph and {NIST ASD Team}},
        langid = {en},
        title = {{NIST} {A}tomic {S}pectra {D}atabase},
        titleaddon = {{NIST} {S}tandard {R}eference {D}atabase 78},
        organization = {National Institute of Standards and Technology},
        note = {Online},
        version = {5.12},
        year = {2024},
        month = nov
    }
    ```

In addition, you can cite `readASD` itself, using the Zenodo DOI identifier:


=== "Cite `readASD`"
    !!! quote "Citation"
        Salden A. (2024)...

=== "BibTeX"
    ```bibtex
    @software{Salden2024readASD,
        doi = {10.5281/ZENODO.},
        url = {https://github.com/AntoineTUE/readasd},
        author = {Salden, Antoine},
        title = {readASD: retrieve data from the NIST ASD, using caching},
        publisher = {Zenodo},
        version = {},
        year = {2024},
    }
    ```
