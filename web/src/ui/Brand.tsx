import mark from '../assets/colabreel.svg'

export const PRODUCT_NAME = 'ColabReel'
export const PRODUCT_TAGLINE = 'From Colab to the next shot.'

export function BrandMark({ large = false }: { large?: boolean }) {
  return <img className={large ? 'brand-mark lg' : 'brand-mark'} src={mark} alt="" aria-hidden="true" />
}
